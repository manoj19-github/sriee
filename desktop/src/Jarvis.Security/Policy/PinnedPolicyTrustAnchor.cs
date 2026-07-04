using System.Collections.Immutable;
using System.Text.RegularExpressions;

namespace Jarvis.Security.Policy;

public sealed partial class PinnedPolicyTrustAnchor
{
    private readonly ImmutableArray<byte> subjectPublicKeyInfo;

    public PinnedPolicyTrustAnchor(
        string keyId,
        ReadOnlySpan<byte> subjectPublicKeyInfo)
    {
        if (!KeyIdPattern().IsMatch(keyId))
        {
            throw new ArgumentException("Invalid policy signing key ID.", nameof(keyId));
        }

        if (subjectPublicKeyInfo.Length is < 32 or > 4096)
        {
            throw new ArgumentException(
                "Invalid policy signing public key.",
                nameof(subjectPublicKeyInfo));
        }

        KeyId = keyId;
        this.subjectPublicKeyInfo = [.. subjectPublicKeyInfo];
    }

    public string KeyId { get; }

    internal byte[] ExportSubjectPublicKeyInfo() => [.. subjectPublicKeyInfo];

    [GeneratedRegex(
        "^[a-z][a-z0-9-]{2,63}$",
        RegexOptions.CultureInvariant,
        matchTimeoutMilliseconds: 100)]
    private static partial Regex KeyIdPattern();
}
