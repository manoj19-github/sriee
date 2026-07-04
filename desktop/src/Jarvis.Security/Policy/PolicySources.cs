namespace Jarvis.Security.Policy;

public interface IPackagedPolicySource
{
    ReadOnlyMemory<byte> ReadPackagedBaseline();
}

public interface ILocalPolicyOverlaySource
{
    ReadOnlyMemory<byte>? ReadAdminOverlay();

    ReadOnlyMemory<byte>? ReadUserOverlay();
}
