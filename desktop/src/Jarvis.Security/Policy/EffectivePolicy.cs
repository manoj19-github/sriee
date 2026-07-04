using System.Collections.Immutable;

namespace Jarvis.Security.Policy;

public sealed record EffectivePolicy
{
    internal EffectivePolicy(
        string policyVersion,
        string signingKeyId,
        string baselineSha256,
        string? adminOverlayVersion,
        string? userOverlayVersion,
        ImmutableDictionary<string, PolicyDecision> rules)
    {
        PolicyVersion = policyVersion;
        SigningKeyId = signingKeyId;
        BaselineSha256 = baselineSha256;
        AdminOverlayVersion = adminOverlayVersion;
        UserOverlayVersion = userOverlayVersion;
        Rules = rules;
    }

    public string PolicyVersion { get; }

    public string SigningKeyId { get; }

    public string BaselineSha256 { get; }

    public string? AdminOverlayVersion { get; }

    public string? UserOverlayVersion { get; }

    public PolicyDecision DefaultDecision => PolicyDecision.Deny;

    public ImmutableDictionary<string, PolicyDecision> Rules { get; }

    public PolicyDecision DecisionFor(string capabilityId)
    {
        if (string.IsNullOrWhiteSpace(capabilityId))
        {
            return PolicyDecision.Deny;
        }

        return Rules.TryGetValue(capabilityId, out PolicyDecision decision)
            ? decision
            : PolicyDecision.Deny;
    }
}
