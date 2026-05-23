using UnityEngine;

/// <summary>
/// Makes the camera always look at a target GameObject.
/// Attach this script to your camera and assign the target object.
/// </summary>
public class CameraLookAt : MonoBehaviour
{
    [SerializeField]
    private Transform target;

    private void LateUpdate()
    {
        if (target != null)
        {
            transform.LookAt(target);
        }
    }
}
