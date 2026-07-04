using System.Collections.Immutable;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Jarvis.Security.Policy;

namespace Jarvis.Security.Tests.Policy;

[TestClass]
public sealed class PolicyBaselineLoaderTests : IDisposable
{
    private const string KeyId = "policy-root-v1";
    private readonly ECDsa signingKey = ECDsa.Create(ECCurve.NamedCurves.nistP256);

    public void Dispose() => signingKey.Dispose();

    [TestMethod]
    public void LoadsSignedDenyByDefaultBaseline()
    {
        PolicyBaselineLoader loader = CreateLoader();

        EffectivePolicy policy = loader.LoadPolicyBaseline();

        Assert.AreEqual("1.0.0", policy.PolicyVersion);
        Assert.AreEqual(KeyId, policy.SigningKeyId);
        Assert.AreEqual(PolicyDecision.Deny, policy.DefaultDecision);
        Assert.AreEqual(
            PolicyDecision.Allow,
            policy.DecisionFor("clock.read"));
        Assert.AreEqual(
            PolicyDecision.Ask,
            policy.DecisionFor("project.write"));
        Assert.AreEqual(
            PolicyDecision.Deny,
            policy.DecisionFor("unknown.capability"));
        Assert.AreEqual(64, policy.BaselineSha256.Length);
        Assert.IsInstanceOfType<
            ImmutableDictionary<string, PolicyDecision>>(policy.Rules);
    }

    [TestMethod]
    public void AdminThenUserOverlaysCanOnlyTighten()
    {
        byte[] admin = Overlay(
            rules: new Dictionary<string, string>
            {
                ["clock.read"] = "ask",
                ["project.write"] = "deny",
            },
            overlayVersion: "1.1.0");
        byte[] user = Overlay(
            rules: new Dictionary<string, string>
            {
                ["clock.read"] = "deny",
            },
            overlayVersion: "1.2.0");

        EffectivePolicy policy = CreateLoader(admin, user).LoadPolicyBaseline();

        Assert.AreEqual(
            PolicyDecision.Deny,
            policy.DecisionFor("clock.read"));
        Assert.AreEqual(
            PolicyDecision.Deny,
            policy.DecisionFor("project.write"));
        Assert.AreEqual("1.1.0", policy.AdminOverlayVersion);
        Assert.AreEqual("1.2.0", policy.UserOverlayVersion);
    }

    [TestMethod]
    public void OverlayCannotRelaxCurrentDecision()
    {
        byte[] overlay = Overlay(
            rules: new Dictionary<string, string>
            {
                ["system.unlock"] = "ask",
            });

        AssertCode(
            "policy_overlay_cannot_relax",
            () => CreateLoader(admin: overlay).LoadPolicyBaseline());
    }

    [TestMethod]
    public void UserOverlayCannotUndoAdminRestriction()
    {
        byte[] admin = Overlay(
            rules: new Dictionary<string, string>
            {
                ["clock.read"] = "deny",
            });
        byte[] user = Overlay(
            rules: new Dictionary<string, string>
            {
                ["clock.read"] = "ask",
            });

        AssertCode(
            "policy_overlay_cannot_relax",
            () => CreateLoader(admin, user).LoadPolicyBaseline());
    }

    [TestMethod]
    public void OverlayCannotIntroduceCapability()
    {
        byte[] overlay = Overlay(
            rules: new Dictionary<string, string>
            {
                ["model.proposed"] = "deny",
            });

        AssertCode(
            "policy_overlay_invalid",
            () => CreateLoader(admin: overlay).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsTamperedPayload()
    {
        byte[] package = Package(BaselinePayload());
        using JsonDocument parsed = JsonDocument.Parse(package);
        JsonElement root = parsed.RootElement;
        byte[] payload = Convert.FromBase64String(
            root.GetProperty("payload").GetString()!);
        payload[0] ^= 1;
        package = JsonSerializer.SerializeToUtf8Bytes(
            new
            {
                envelopeVersion = "1",
                keyId = KeyId,
                payload = Convert.ToBase64String(payload),
                signature = root.GetProperty("signature").GetString(),
            });

        AssertCode(
            "policy_signature_invalid",
            () => CreateLoader(package: package).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsSignatureFromAnotherKey()
    {
        using ECDsa other = ECDsa.Create(ECCurve.NamedCurves.nistP256);
        byte[] package = Package(BaselinePayload(), signer: other);

        AssertCode(
            "policy_signature_invalid",
            () => CreateLoader(package: package).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsUnknownSigningKeyId()
    {
        byte[] package = Package(
            BaselinePayload(),
            keyId: "policy-root-v2");

        AssertCode(
            "policy_signature_invalid",
            () => CreateLoader(package: package).LoadPolicyBaseline());
    }

    [TestMethod]
    public void SignatureBindsEnvelopeMetadata()
    {
        byte[] package = Package(BaselinePayload());
        string json = Encoding.UTF8.GetString(package).Replace(
            "\"envelopeVersion\":\"1\"",
            "\"envelopeVersion\":\"2\"",
            StringComparison.Ordinal);

        AssertCode(
            "policy_envelope_version_unsupported",
            () => CreateLoader(
                package: Encoding.UTF8.GetBytes(json)).LoadPolicyBaseline());
    }

    [TestMethod]
    [DataRow("2", "1.0.0")]
    [DataRow("1", "2.0.0")]
    [DataRow("1", "1.0")]
    [DataRow("1", "01.0.0")]
    public void RejectsUnsupportedOrNoncanonicalPolicyVersion(
        string schemaVersion,
        string policyVersion)
    {
        byte[] payload = BaselinePayload(
            schemaVersion: schemaVersion,
            policyVersion: policyVersion);

        AssertCode(
            "policy_version_unsupported",
            () => CreateLoader(
                package: Package(payload)).LoadPolicyBaseline());
    }

    [TestMethod]
    public void BaselineDefaultMustBeDeny()
    {
        byte[] payload = BaselinePayload(defaultDecision: "ask");

        AssertCode(
            "policy_default_must_deny",
            () => CreateLoader(
                package: Package(payload)).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsDuplicateEnvelopeProperty()
    {
        byte[] valid = Package(BaselinePayload());
        string json = Encoding.UTF8.GetString(valid).Replace(
            "{\"envelopeVersion\":\"1\",",
            "{\"envelopeVersion\":\"1\",\"envelopeVersion\":\"1\",",
            StringComparison.Ordinal);

        AssertCode(
            "policy_package_invalid",
            () => CreateLoader(
                package: Encoding.UTF8.GetBytes(json)).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsDuplicatePayloadRule()
    {
        const string payload =
            """
            {"schemaVersion":"1","policyVersion":"1.0.0",
            "defaultDecision":"deny","rules":{"clock.read":"allow",
            "clock.read":"deny"}}
            """;

        AssertCode(
            "policy_document_invalid",
            () => CreateLoader(
                package: Package(
                    Encoding.UTF8.GetBytes(payload))).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsUnknownFieldsAndIntegerEnums()
    {
        const string unknown =
            """
            {"schemaVersion":"1","policyVersion":"1.0.0",
            "defaultDecision":"deny","rules":{},"extra":true}
            """;
        const string numeric =
            """
            {"schemaVersion":"1","policyVersion":"1.0.0",
            "defaultDecision":0,"rules":{}}
            """;

        AssertCode(
            "policy_document_invalid",
            () => CreateLoader(
                package: Package(
                    Encoding.UTF8.GetBytes(unknown))).LoadPolicyBaseline());
        AssertCode(
            "policy_document_invalid",
            () => CreateLoader(
                package: Package(
                    Encoding.UTF8.GetBytes(numeric))).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsMalformedAndOversizedPackages()
    {
        AssertCode(
            "policy_package_invalid",
            () => CreateLoader(package: "{"u8.ToArray()).LoadPolicyBaseline());
        AssertCode(
            "policy_package_invalid",
            () => CreateLoader(
                package: new byte[65_537]).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsInvalidCapabilityAndRuleLimit()
    {
        var invalid = new Dictionary<string, string>
        {
            ["INVALID CAPABILITY"] = "deny",
        };
        var excessive = Enumerable.Range(0, 257).ToDictionary(
            index => $"capability.{index:D3}",
            _ => "deny",
            StringComparer.Ordinal);

        AssertCode(
            "policy_rules_invalid",
            () => CreateLoader(
                package: Package(
                    BaselinePayload(rules: invalid))).LoadPolicyBaseline());
        AssertCode(
            "policy_rules_invalid",
            () => CreateLoader(
                package: Package(
                    BaselinePayload(rules: excessive))).LoadPolicyBaseline());
    }

    [TestMethod]
    public void OverlayMustTargetExactBaseline()
    {
        byte[] overlay = Overlay(baselineVersion: "1.0.1");

        AssertCode(
            "policy_overlay_baseline_mismatch",
            () => CreateLoader(admin: overlay).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsUnknownOverlayVersionAndDuplicateRule()
    {
        byte[] version = Overlay(schemaVersion: "2");
        const string duplicate =
            """
            {"schemaVersion":"1","baselinePolicyVersion":"1.0.0",
            "overlayVersion":"1.0.0","rules":{"clock.read":"ask",
            "clock.read":"deny"}}
            """;

        AssertCode(
            "policy_overlay_version_unsupported",
            () => CreateLoader(admin: version).LoadPolicyBaseline());
        AssertCode(
            "policy_overlay_invalid",
            () => CreateLoader(
                admin: Encoding.UTF8.GetBytes(
                    duplicate)).LoadPolicyBaseline());
    }

    [TestMethod]
    public void RejectsOversizedOverlay()
    {
        AssertCode(
            "policy_overlay_invalid",
            () => CreateLoader(
                admin: new byte[16_385]).LoadPolicyBaseline());
    }

    [TestMethod]
    public void SourceFailuresAreSanitized()
    {
        var source = new Source(
            Package(BaselinePayload()),
            error: new InvalidOperationException("private path detail"));
        var loader = new PolicyBaselineLoader(
            source,
            source,
            TrustAnchor());

        PolicyLoadException error = Assert.Throws<PolicyLoadException>(
            loader.LoadPolicyBaseline);

        Assert.AreEqual("policy_source_unavailable", error.Code);
        Assert.DoesNotContain("private path detail", error.Message);
    }

    [TestMethod]
    public void BaselineHashIsDeterministicAndRawDocumentsAreNotRetained()
    {
        byte[] payload = BaselinePayload();
        EffectivePolicy first = CreateLoader(
            package: Package(payload)).LoadPolicyBaseline();
        EffectivePolicy second = CreateLoader(
            package: Package(payload)).LoadPolicyBaseline();

        Assert.AreEqual(first.BaselineSha256, second.BaselineSha256);
        Assert.AreEqual(
            Convert.ToHexStringLower(SHA256.HashData(payload)),
            first.BaselineSha256);
        Assert.IsFalse(
            typeof(EffectivePolicy)
                .GetProperties()
                .Any(property => property.PropertyType == typeof(byte[])));
    }

    [TestMethod]
    public void EmptyRulesRemainDenyByDefault()
    {
        byte[] payload = BaselinePayload(
            rules: new Dictionary<string, string>());

        EffectivePolicy policy = CreateLoader(
            package: Package(payload)).LoadPolicyBaseline();

        Assert.IsEmpty(policy.Rules);
        Assert.AreEqual(
            PolicyDecision.Deny,
            policy.DecisionFor("anything.requested"));
        Assert.AreEqual(PolicyDecision.Deny, policy.DecisionFor(string.Empty));
    }

    [TestMethod]
    public void SnapshotsEachTrustedSourceBeforeReadingTheNext()
    {
        byte[] baseline = Package(BaselinePayload());
        byte[] admin = Overlay(
            rules: new Dictionary<string, string>
            {
                ["clock.read"] = "ask",
            });
        var source = new MutatingSource(baseline, admin);
        var loader = new PolicyBaselineLoader(
            source,
            source,
            TrustAnchor());

        EffectivePolicy policy = loader.LoadPolicyBaseline();

        Assert.AreEqual(
            PolicyDecision.Ask,
            policy.DecisionFor("clock.read"));
    }

    private PolicyBaselineLoader CreateLoader(
        byte[]? admin = null,
        byte[]? user = null,
        byte[]? package = null)
    {
        var source = new Source(
            package ?? Package(BaselinePayload()),
            admin,
            user);
        return new PolicyBaselineLoader(source, source, TrustAnchor());
    }

    private PinnedPolicyTrustAnchor TrustAnchor() =>
        new(KeyId, signingKey.ExportSubjectPublicKeyInfo());

    private byte[] Package(
        byte[] payload,
        ECDsa? signer = null,
        string keyId = KeyId,
        string envelopeVersion = "1")
    {
        signer ??= signingKey;
        byte[] message = SignatureMessage(
            envelopeVersion,
            keyId,
            payload);
        byte[] signature = signer.SignData(
            message,
            HashAlgorithmName.SHA256,
            DSASignatureFormat.Rfc3279DerSequence);
        return JsonSerializer.SerializeToUtf8Bytes(
            new
            {
                envelopeVersion,
                keyId,
                payload = Convert.ToBase64String(payload),
                signature = Convert.ToBase64String(signature),
            });
    }

    private static byte[] SignatureMessage(
        string envelopeVersion,
        string keyId,
        byte[] payload)
    {
        byte[] prefix = Encoding.UTF8.GetBytes(
            $"JARVIS-POLICY-BASELINE-V1\0{envelopeVersion}\0{keyId}\0");
        return [.. prefix, .. payload];
    }

    private static byte[] BaselinePayload(
        string schemaVersion = "1",
        string policyVersion = "1.0.0",
        string defaultDecision = "deny",
        Dictionary<string, string>? rules = null)
    {
        rules ??= new Dictionary<string, string>
        {
            ["clock.read"] = "allow",
            ["project.write"] = "ask",
            ["system.unlock"] = "deny",
        };
        return JsonSerializer.SerializeToUtf8Bytes(
            new
            {
                schemaVersion,
                policyVersion,
                defaultDecision,
                rules,
            });
    }

    private static byte[] Overlay(
        Dictionary<string, string>? rules = null,
        string schemaVersion = "1",
        string baselineVersion = "1.0.0",
        string overlayVersion = "1.0.0")
    {
        rules ??= new Dictionary<string, string>();
        return JsonSerializer.SerializeToUtf8Bytes(
            new
            {
                schemaVersion,
                baselinePolicyVersion = baselineVersion,
                overlayVersion,
                rules,
            });
    }

    private static void AssertCode(string code, Action action)
    {
        PolicyLoadException error =
            Assert.Throws<PolicyLoadException>(action);
        Assert.AreEqual(code, error.Code);
    }

    private sealed class Source :
        IPackagedPolicySource,
        ILocalPolicyOverlaySource
    {
        private readonly byte[] baseline;
        private readonly byte[]? admin;
        private readonly byte[]? user;
        private readonly Exception? error;

        public Source(
            byte[] baseline,
            byte[]? admin = null,
            byte[]? user = null,
            Exception? error = null)
        {
            this.baseline = baseline;
            this.admin = admin;
            this.user = user;
            this.error = error;
        }

        public ReadOnlyMemory<byte> ReadPackagedBaseline()
        {
            if (error is not null)
            {
                throw error;
            }

            return baseline;
        }

        public ReadOnlyMemory<byte>? ReadAdminOverlay()
        {
            return admin is null
                ? (ReadOnlyMemory<byte>?)null
                : new ReadOnlyMemory<byte>(admin);
        }

        public ReadOnlyMemory<byte>? ReadUserOverlay()
        {
            return user is null
                ? (ReadOnlyMemory<byte>?)null
                : new ReadOnlyMemory<byte>(user);
        }
    }

    private sealed class MutatingSource :
        IPackagedPolicySource,
        ILocalPolicyOverlaySource
    {
        private readonly byte[] baseline;
        private readonly byte[] admin;

        public MutatingSource(byte[] baseline, byte[] admin)
        {
            this.baseline = baseline;
            this.admin = admin;
        }

        public ReadOnlyMemory<byte> ReadPackagedBaseline() => baseline;

        public ReadOnlyMemory<byte>? ReadAdminOverlay()
        {
            baseline.AsSpan().Fill(0);
            return admin;
        }

        public ReadOnlyMemory<byte>? ReadUserOverlay()
        {
            admin.AsSpan().Fill(0);
            return null;
        }
    }
}
