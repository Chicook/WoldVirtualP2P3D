using UnityEngine;
using UnityEngine.UI;
#if UNITY_WEBGL && !UNITY_EDITOR
using System.Runtime.InteropServices;
#endif

public class AddTokenToMetaMask : MonoBehaviour
{
    public void OnAddTokenClicked()
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        AddTokenToMetaMaskWebGL();
#else
        Debug.LogWarning("Token addition to MetaMask is only supported in WebGL builds.");
        // Optionally show a UI message to the user
#endif
    }

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")]
    private static extern void AddTokenToMetaMaskWebGL();
#endif
}