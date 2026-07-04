using System.Collections.Immutable;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace Jarvis.Security.Policy;

public sealed partial class PolicyBaselineLoader
{
    private const int MaximumBaselineBytes = 65_536;
    private const int MaximumOverlayBytes = 16_384;
    private const int MaximumRules = 256;
    private const string SupportedEnvelopeVersion = "1";
    private const string SupportedSchemaVersion = "1";
    private static readonly byte[] SignatureDomain =
        "JARVIS-POLICY-BASELINE-V1\0"u8.ToArray();

    private static readonly JsonSerializerOptions JsonOptions = CreateJsonOptions();

    private readonly IPackagedPolicySource baselineSource;
    private readonly ILocalPolicyOverlaySource overlaySource;
    private readonly PinnedPolicyTrustAnchor trustAnchor;

    public PolicyBaselineLoader(
        IPackagedPolicySource baselineSource,
        ILocalPolicyOverlaySource overlaySource,
        PinnedPolicyTrustAnchor trustAnchor)
    {
        this.baselineSource =
            baselineSource ?? throw new ArgumentNullException(nameof(baselineSource));
        this.overlaySource =
            overlaySource ?? throw new ArgumentNullException(nameof(overlaySource));
        this.trustAnchor =
            trustAnchor ?? throw new ArgumentNullException(nameof(trustAnchor));
    }

    public EffectivePolicy LoadPolicyBaseline()
    {
        ReadOnlyMemory<byte> packagedBaseline = SnapshotDocument(
            ReadSource(baselineSource.ReadPackagedBaseline),
            MaximumBaselineBytes,
            "policy_package_invalid");
        ReadOnlyMemory<byte>? rawAdminOverlay =
            ReadSource(overlaySource.ReadAdminOverlay);
        ReadOnlyMemory<byte>? adminOverlay = rawAdminOverlay is null
            ? (ReadOnlyMemory<byte>?)null
            : SnapshotDocument(
                rawAdminOverlay.Value,
                MaximumOverlayBytes,
                "policy_overlay_invalid");
        ReadOnlyMemory<byte>? rawUserOverlay =
            ReadSource(overlaySource.ReadUserOverlay);
        ReadOnlyMemory<byte>? userOverlay = rawUserOverlay is null
            ? (ReadOnlyMemory<byte>?)null
            : SnapshotDocument(
                rawUserOverlay.Value,
                MaximumOverlayBytes,
                "policy_overlay_invalid");

        VerifiedBaseline verified = VerifyAndParseBaseline(packagedBaseline);
        ImmutableDictionary<string, PolicyDecision> rules =
            ValidateBaseline(verified.Document);

        string? adminVersion = null;
        string? userVersion = null;
        if (adminOverlay is not null)
        {
            PolicyOverlayDocument overlay = ParseOverlay(adminOverlay.Value);
            rules = ApplyTighteningOverlay(
                rules,
                verified.Document.PolicyVersion,
                overlay);
            adminVersion = overlay.OverlayVersion;
        }

        if (userOverlay is not null)
        {
            PolicyOverlayDocument overlay = ParseOverlay(userOverlay.Value);
            rules = ApplyTighteningOverlay(
                rules,
                verified.Document.PolicyVersion,
                overlay);
            userVersion = overlay.OverlayVersion;
        }

        return new EffectivePolicy(
            verified.Document.PolicyVersion,
            trustAnchor.KeyId,
            Convert.ToHexStringLower(SHA256.HashData(verified.Payload.Span)),
            adminVersion,
            userVersion,
            rules);
    }

    private static T ReadSource<T>(Func<T> read)
    {
        try
        {
            return read();
        }
        catch (Exception exception) when (
            exception is not OutOfMemoryException
            and not StackOverflowException)
        {
            throw new PolicyLoadException("policy_source_unavailable");
        }
    }

    private VerifiedBaseline VerifyAndParseBaseline(
        ReadOnlyMemory<byte> packagedBaseline)
    {
        if (packagedBaseline.Length is < 2 or > MaximumBaselineBytes)
        {
            throw new PolicyLoadException("policy_package_invalid");
        }

        SignedPolicyEnvelope envelope = DeserializeStrict<SignedPolicyEnvelope>(
            packagedBaseline.Span,
            "policy_package_invalid");
        if (!string.Equals(
                envelope.EnvelopeVersion,
                SupportedEnvelopeVersion,
                StringComparison.Ordinal))
        {
            throw new PolicyLoadException("policy_envelope_version_unsupported");
        }

        if (!string.Equals(
                envelope.KeyId,
                trustAnchor.KeyId,
                StringComparison.Ordinal))
        {
            throw new PolicyLoadException("policy_signature_invalid");
        }

        byte[] payload = DecodeCanonicalBase64(
            envelope.Payload,
            MaximumBaselineBytes,
            "policy_package_invalid");
        byte[] signature = DecodeCanonicalBase64(
            envelope.Signature,
            256,
            "policy_signature_invalid");
        VerifySignature(envelope.EnvelopeVersion, envelope.KeyId, payload, signature);

        PolicyBaselineDocument document =
            DeserializeStrict<PolicyBaselineDocument>(
                payload,
                "policy_document_invalid");
        return new VerifiedBaseline(document, payload);
    }

    private void VerifySignature(
        string envelopeVersion,
        string keyId,
        ReadOnlySpan<byte> payload,
        ReadOnlySpan<byte> signature)
    {
        byte[] message = BuildSignatureMessage(envelopeVersion, keyId, payload);
        try
        {
            using ECDsa verifier = ECDsa.Create();
            byte[] publicKey = trustAnchor.ExportSubjectPublicKeyInfo();
            verifier.ImportSubjectPublicKeyInfo(publicKey, out int bytesRead);
            if (bytesRead != publicKey.Length || verifier.KeySize != 256)
            {
                throw new PolicyLoadException("policy_signature_invalid");
            }

            if (!verifier.VerifyData(
                    message,
                    signature,
                    HashAlgorithmName.SHA256,
                    DSASignatureFormat.Rfc3279DerSequence))
            {
                throw new PolicyLoadException("policy_signature_invalid");
            }
        }
        catch (PolicyLoadException)
        {
            throw;
        }
        catch (CryptographicException)
        {
            throw new PolicyLoadException("policy_signature_invalid");
        }
        finally
        {
            CryptographicOperations.ZeroMemory(message);
        }
    }

    private static ImmutableDictionary<string, PolicyDecision> ValidateBaseline(
        PolicyBaselineDocument document)
    {
        ValidatePolicyVersion(
            document.SchemaVersion,
            document.PolicyVersion,
            "policy_version_unsupported");
        if (document.DefaultDecision is not PolicyDecision.Deny)
        {
            throw new PolicyLoadException("policy_default_must_deny");
        }

        if (document.Rules is null || document.Rules.Count > MaximumRules)
        {
            throw new PolicyLoadException("policy_rules_invalid");
        }

        var builder = ImmutableDictionary.CreateBuilder<
            string,
            PolicyDecision>(StringComparer.Ordinal);
        foreach (
            KeyValuePair<string, PolicyDecision> rule
            in document.Rules.OrderBy(
                pair => pair.Key,
                StringComparer.Ordinal))
        {
            if (!CapabilityPattern().IsMatch(rule.Key))
            {
                throw new PolicyLoadException("policy_rules_invalid");
            }

            builder.Add(rule.Key, rule.Value);
        }

        return builder.ToImmutable();
    }

    private static PolicyOverlayDocument ParseOverlay(
        ReadOnlyMemory<byte> rawOverlay)
    {
        if (rawOverlay.Length is < 2 or > MaximumOverlayBytes)
        {
            throw new PolicyLoadException("policy_overlay_invalid");
        }

        PolicyOverlayDocument overlay =
            DeserializeStrict<PolicyOverlayDocument>(
                rawOverlay.Span,
                "policy_overlay_invalid");
        ValidatePolicyVersion(
            overlay.SchemaVersion,
            overlay.OverlayVersion,
            "policy_overlay_version_unsupported");
        if (overlay.Rules is null || overlay.Rules.Count > MaximumRules)
        {
            throw new PolicyLoadException("policy_overlay_invalid");
        }

        return overlay;
    }

    private static ImmutableDictionary<string, PolicyDecision>
        ApplyTighteningOverlay(
            ImmutableDictionary<string, PolicyDecision> current,
            string baselinePolicyVersion,
            PolicyOverlayDocument overlay)
    {
        if (!string.Equals(
                overlay.BaselinePolicyVersion,
                baselinePolicyVersion,
                StringComparison.Ordinal))
        {
            throw new PolicyLoadException("policy_overlay_baseline_mismatch");
        }

        ImmutableDictionary<string, PolicyDecision>.Builder builder =
            current.ToBuilder();
        foreach (
            KeyValuePair<string, PolicyDecision> rule
            in overlay.Rules.OrderBy(
                pair => pair.Key,
                StringComparer.Ordinal))
        {
            if (!CapabilityPattern().IsMatch(rule.Key)
                || !builder.TryGetValue(
                    rule.Key,
                    out PolicyDecision currentDecision))
            {
                throw new PolicyLoadException("policy_overlay_invalid");
            }

            if (rule.Value > currentDecision)
            {
                throw new PolicyLoadException("policy_overlay_cannot_relax");
            }

            builder[rule.Key] = rule.Value;
        }

        return builder.ToImmutable();
    }

    private static T DeserializeStrict<T>(
        ReadOnlySpan<byte> json,
        string errorCode)
    {
        try
        {
            using JsonDocument parsed = JsonDocument.Parse(
                json.ToArray(),
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow,
                    MaxDepth = 16,
                });
            RejectDuplicateProperties(parsed.RootElement);
            return JsonSerializer.Deserialize<T>(json, JsonOptions)
                ?? throw new JsonException("Document cannot be null.");
        }
        catch (JsonException)
        {
            throw new PolicyLoadException(errorCode);
        }
    }

    private static void RejectDuplicateProperties(JsonElement element)
    {
        if (element.ValueKind is JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (!names.Add(property.Name))
                {
                    throw new JsonException("Duplicate property.");
                }

                RejectDuplicateProperties(property.Value);
            }
        }
        else if (element.ValueKind is JsonValueKind.Array)
        {
            foreach (JsonElement item in element.EnumerateArray())
            {
                RejectDuplicateProperties(item);
            }
        }
    }

    private static byte[] DecodeCanonicalBase64(
        string value,
        int maximumBytes,
        string errorCode)
    {
        if (string.IsNullOrEmpty(value)
            || value.Length > ((maximumBytes + 2) / 3 * 4))
        {
            throw new PolicyLoadException(errorCode);
        }

        try
        {
            byte[] decoded = Convert.FromBase64String(value);
            if (decoded.Length > maximumBytes
                || !string.Equals(
                    Convert.ToBase64String(decoded),
                    value,
                    StringComparison.Ordinal))
            {
                throw new PolicyLoadException(errorCode);
            }

            return decoded;
        }
        catch (FormatException)
        {
            throw new PolicyLoadException(errorCode);
        }
    }

    private static ReadOnlyMemory<byte> SnapshotDocument(
        ReadOnlyMemory<byte> document,
        int maximumBytes,
        string errorCode)
    {
        if (document.Length is < 2 || document.Length > maximumBytes)
        {
            throw new PolicyLoadException(errorCode);
        }

        return document.ToArray();
    }

    private static void ValidatePolicyVersion(
        string schemaVersion,
        string policyVersion,
        string errorCode)
    {
        if (!string.Equals(
                schemaVersion,
                SupportedSchemaVersion,
                StringComparison.Ordinal)
            || !PolicyVersionPattern().IsMatch(policyVersion)
            || !policyVersion.StartsWith("1.", StringComparison.Ordinal))
        {
            throw new PolicyLoadException(errorCode);
        }
    }

    private static byte[] BuildSignatureMessage(
        string envelopeVersion,
        string keyId,
        ReadOnlySpan<byte> payload)
    {
        byte[] version = Encoding.UTF8.GetBytes(envelopeVersion);
        byte[] key = Encoding.UTF8.GetBytes(keyId);
        byte[] message = new byte[
            SignatureDomain.Length
            + version.Length
            + 1
            + key.Length
            + 1
            + payload.Length];
        int offset = 0;
        SignatureDomain.CopyTo(message, offset);
        offset += SignatureDomain.Length;
        version.CopyTo(message, offset);
        offset += version.Length;
        message[offset++] = 0;
        key.CopyTo(message, offset);
        offset += key.Length;
        message[offset++] = 0;
        payload.CopyTo(message.AsSpan(offset));
        return message;
    }

    private static JsonSerializerOptions CreateJsonOptions()
    {
        var options = new JsonSerializerOptions
        {
            AllowTrailingCommas = false,
            PropertyNameCaseInsensitive = false,
            ReadCommentHandling = JsonCommentHandling.Disallow,
            UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
        };
        options.Converters.Add(
            new JsonStringEnumConverter(
                JsonNamingPolicy.CamelCase,
                allowIntegerValues: false));
        return options;
    }

    [GeneratedRegex(
        "^[a-z][a-z0-9_.-]{2,127}$",
        RegexOptions.CultureInvariant,
        matchTimeoutMilliseconds: 100)]
    private static partial Regex CapabilityPattern();

    [GeneratedRegex(
        "^(?:0|[1-9][0-9]{0,9})\\."
        + "(?:0|[1-9][0-9]{0,9})\\."
        + "(?:0|[1-9][0-9]{0,9})$",
        RegexOptions.CultureInvariant,
        matchTimeoutMilliseconds: 100)]
    private static partial Regex PolicyVersionPattern();

    private sealed record VerifiedBaseline(
        PolicyBaselineDocument Document,
        ReadOnlyMemory<byte> Payload);

    private sealed record SignedPolicyEnvelope
    {
        [JsonPropertyName("envelopeVersion")]
        public required string EnvelopeVersion { get; init; }

        [JsonPropertyName("keyId")]
        public required string KeyId { get; init; }

        [JsonPropertyName("payload")]
        public required string Payload { get; init; }

        [JsonPropertyName("signature")]
        public required string Signature { get; init; }
    }

    private sealed record PolicyBaselineDocument
    {
        [JsonPropertyName("schemaVersion")]
        public required string SchemaVersion { get; init; }

        [JsonPropertyName("policyVersion")]
        public required string PolicyVersion { get; init; }

        [JsonPropertyName("defaultDecision")]
        public required PolicyDecision DefaultDecision { get; init; }

        [JsonPropertyName("rules")]
        public required Dictionary<string, PolicyDecision> Rules { get; init; }
    }

    private sealed record PolicyOverlayDocument
    {
        [JsonPropertyName("schemaVersion")]
        public required string SchemaVersion { get; init; }

        [JsonPropertyName("baselinePolicyVersion")]
        public required string BaselinePolicyVersion { get; init; }

        [JsonPropertyName("overlayVersion")]
        public required string OverlayVersion { get; init; }

        [JsonPropertyName("rules")]
        public required Dictionary<string, PolicyDecision> Rules { get; init; }
    }
}
