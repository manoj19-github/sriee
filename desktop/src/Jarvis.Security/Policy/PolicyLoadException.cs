namespace Jarvis.Security.Policy;

public sealed class PolicyLoadException : Exception
{
    public PolicyLoadException(string code)
        : base($"JARVIS policy baseline load failed: {code}")
    {
        Code = code;
    }

    public string Code { get; }
}
