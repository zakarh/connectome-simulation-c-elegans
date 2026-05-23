using System;
using System.Collections.Generic;
using UnityEngine;

public sealed class NematodeBodyController : MonoBehaviour
{
    private const float TwoPi = Mathf.PI * 2f;

    [SerializeField] private ConnectomeSimulator simulator;
    [SerializeField] private bool buildOnStart = true;
    [SerializeField] private int segmentCount = 32;
    [SerializeField] private int radialResolution = 12;
    [SerializeField] private float bodyLength = 10f;
    [SerializeField] private float bodyRadius = 0.18f;
    [SerializeField] private float baselineUndulation = 0f;
    [SerializeField] private float undulationCycles = 1.6f;
    [SerializeField] private float undulationFrequency = 0.55f;
    [SerializeField] private float neuralBendGain = 0.35f;
    [SerializeField] private float contractionScale = 0.22f;
    [SerializeField] private float driveDecay = 9f;

    [Header("Physics")]
    [SerializeField] private bool useGravity = true;
    [SerializeField] private float rigidbodyMass = 0.05f;
    [SerializeField] private float colliderRadiusPadding = 1.35f;
    [SerializeField] private bool freezePhysicsRotation;
    [SerializeField] private float musclePullForce = 0.015f;
    [SerializeField] private float jointSpring = 35f;
    [SerializeField] private float jointDamping = 3f;
    [SerializeField] private float jointMaxForce = 5f;
    [SerializeField] private bool showSegmentBodies;

    [Header("Materials")]
    [SerializeField] private Material bodyMaterial;
    [SerializeField] private Material dorsalMuscleMaterial;
    [SerializeField] private Material ventralMuscleMaterial;

    public bool IsBuilt { get; private set; }

    private readonly List<MuscleProjection> muscleProjections = new List<MuscleProjection>();
    private Mesh bodyMesh;
    private Vector3[] vertices = new Vector3[0];
    private int[] triangles = new int[0];
    private Vector3[] centerline = new Vector3[0];
    private float[] dorsalDrive = new float[0];
    private float[] ventralDrive = new float[0];
    private float[] smoothedDorsalDrive = new float[0];
    private float[] smoothedVentralDrive = new float[0];
    private LineRenderer dorsalBand;
    private LineRenderer ventralBand;
    private Transform bodyRoot;
    private Transform physicsRoot;
    private Rigidbody[] segmentBodies = new Rigidbody[0];
    private CapsuleCollider[] segmentColliders = new CapsuleCollider[0];
    private float segmentSpacing;

    private enum MuscleSide
    {
        Dorsal,
        Ventral,
    }

    private struct MuscleProjection
    {
        public string SourceId;
        public int SegmentIndex;
        public MuscleSide Side;
        public float Sign;
        public float Weight;
    }

    private void Start()
    {
        if (buildOnStart)
        {
            Build();
        }
    }

    private void Update()
    {
        if (!IsBuilt)
        {
            return;
        }

        UpdateMuscleDrive(Time.deltaTime);
        UpdateBodyMesh(Time.time);
    }

    private void FixedUpdate()
    {
        if (!IsBuilt || !HasSegmentPhysics)
        {
            return;
        }

        ApplyMuscleForces(Time.fixedTime);
    }

    public void Build()
    {
        if (simulator == null)
        {
            simulator = GetComponent<ConnectomeSimulator>();
        }

        if (simulator == null)
        {
            Debug.LogError("NematodeBodyController needs a ConnectomeSimulator.");
            return;
        }

        if (simulator.Payload == null)
        {
            simulator.Load();
        }

        segmentCount = Mathf.Max(4, segmentCount);
        radialResolution = Mathf.Max(6, radialResolution);

        Clear();
        EnsureMaterials();
        AllocateBuffers();
        BuildMotorMap();
        CreateBodyObjects();
        CreateSegmentedPhysics();
        UpdateBodyMesh(0f);

        IsBuilt = true;
    }

    public Vector3 GetBodySpacePosition(float bodyFraction, float dorsalVentralOffset, float leftRightOffset)
    {
        if (centerline.Length == 0)
        {
            float x = (Mathf.Clamp01(bodyFraction) - 0.5f) * bodyLength;
            return new Vector3(x, dorsalVentralOffset, leftRightOffset);
        }

        float scaled = Mathf.Clamp01(bodyFraction) * (centerline.Length - 1);
        int lower = Mathf.FloorToInt(scaled);
        int upper = Mathf.Min(lower + 1, centerline.Length - 1);
        float blend = scaled - lower;
        Vector3 center = Vector3.Lerp(centerline[lower], centerline[upper], blend);
        Vector3 up = Vector3.up;
        Vector3 right = Vector3.forward;

        if (HasSegmentPhysics)
        {
            Transform lowerSegment = segmentBodies[lower].transform;
            Transform upperSegment = segmentBodies[upper].transform;
            up = Vector3.Slerp(
                BodyRootDirection(lowerSegment.up),
                BodyRootDirection(upperSegment.up),
                blend
            ).normalized;
            right = Vector3.Slerp(
                BodyRootDirection(lowerSegment.forward),
                BodyRootDirection(upperSegment.forward),
                blend
            ).normalized;
        }

        return center + up * dorsalVentralOffset + right * leftRightOffset;
    }

    private bool HasSegmentPhysics =>
        segmentBodies != null
        && segmentBodies.Length == segmentCount
        && segmentBodies[0] != null;

    private void AllocateBuffers()
    {
        int vertexCount = segmentCount * radialResolution;
        vertices = new Vector3[vertexCount];
        centerline = new Vector3[segmentCount];
        dorsalDrive = new float[segmentCount];
        ventralDrive = new float[segmentCount];
        smoothedDorsalDrive = new float[segmentCount];
        smoothedVentralDrive = new float[segmentCount];
        triangles = new int[(segmentCount - 1) * radialResolution * 6];
    }

    private void BuildMotorMap()
    {
        muscleProjections.Clear();

        if (simulator.Payload == null || simulator.Payload.edges == null)
        {
            return;
        }

        float maxWeight = 1f;
        foreach (ConnectomeEdge edge in simulator.Payload.edges)
        {
            if (edge.kind != "neuromuscular")
            {
                continue;
            }

            maxWeight = Mathf.Max(maxWeight, edge.weight);
        }

        foreach (ConnectomeEdge edge in simulator.Payload.edges)
        {
            if (edge.kind != "neuromuscular")
            {
                continue;
            }

            if (!TryCreateMuscleProjection(edge, maxWeight, out MuscleProjection projection))
            {
                continue;
            }

            muscleProjections.Add(projection);
        }
    }

    private bool TryCreateMuscleProjection(ConnectomeEdge edge, float maxWeight, out MuscleProjection projection)
    {
        projection = new MuscleProjection();

        if (!TryParseMotorNeuron(edge.source, out string neuronClass, out int segment))
        {
            return false;
        }

        if (!TryMapMotorClass(neuronClass, out MuscleSide side, out float sign))
        {
            return false;
        }

        projection = new MuscleProjection
        {
            SourceId = edge.source,
            SegmentIndex = MotorSegmentToBodyIndex(neuronClass, segment),
            Side = side,
            Sign = sign,
            Weight = Mathf.Clamp01(edge.weight / maxWeight),
        };
        return true;
    }

    private bool TryParseMotorNeuron(string sourceId, out string neuronClass, out int segment)
    {
        neuronClass = "";
        segment = 0;

        int digitStart = sourceId.Length;
        for (int i = sourceId.Length - 1; i >= 0; i--)
        {
            if (!char.IsDigit(sourceId[i]))
            {
                break;
            }

            digitStart = i;
        }

        if (digitStart == sourceId.Length || digitStart == 0)
        {
            return false;
        }

        neuronClass = sourceId.Substring(0, digitStart);
        return int.TryParse(sourceId.Substring(digitStart), out segment);
    }

    private bool TryMapMotorClass(string neuronClass, out MuscleSide side, out float sign)
    {
        side = MuscleSide.Ventral;
        sign = 1f;

        if (neuronClass == "DA" || neuronClass == "DB" || neuronClass == "AS")
        {
            side = MuscleSide.Dorsal;
            return true;
        }

        if (neuronClass == "VA" || neuronClass == "VB" || neuronClass == "VC")
        {
            side = MuscleSide.Ventral;
            return true;
        }

        if (neuronClass == "DD")
        {
            side = MuscleSide.Dorsal;
            sign = -1f;
            return true;
        }

        if (neuronClass == "VD")
        {
            side = MuscleSide.Ventral;
            sign = -1f;
            return true;
        }

        return false;
    }

    private int MotorSegmentToBodyIndex(string neuronClass, int segment)
    {
        int maxSegment = MaxSegmentForClass(neuronClass);
        float fraction = 0.14f + 0.78f * ((Mathf.Clamp(segment, 1, maxSegment) - 0.5f) / maxSegment);
        return Mathf.Clamp(Mathf.RoundToInt(fraction * (segmentCount - 1)), 0, segmentCount - 1);
    }

    private int MaxSegmentForClass(string neuronClass)
    {
        if (neuronClass == "AS" || neuronClass == "VB")
        {
            return 11;
        }

        if (neuronClass == "DA")
        {
            return 9;
        }

        if (neuronClass == "DB" || neuronClass == "VC")
        {
            return 7;
        }

        if (neuronClass == "DD")
        {
            return 6;
        }

        if (neuronClass == "VD")
        {
            return 13;
        }

        return 12;
    }

    private void CreateBodyObjects()
    {
        bodyRoot = new GameObject("Nematode Body").transform;
        bodyRoot.SetParent(transform, false);

        GameObject meshObject = new GameObject("Body Mesh");
        meshObject.transform.SetParent(bodyRoot, false);

        MeshFilter meshFilter = meshObject.AddComponent<MeshFilter>();
        MeshRenderer meshRenderer = meshObject.AddComponent<MeshRenderer>();
        bodyMesh = new Mesh
        {
            name = "Generated C elegans Body",
        };
        meshFilter.sharedMesh = bodyMesh;
        meshRenderer.sharedMaterial = bodyMaterial;

        BuildTriangles();

        dorsalBand = CreateMuscleBand("Dorsal Muscle Band", dorsalMuscleMaterial);
        ventralBand = CreateMuscleBand("Ventral Muscle Band", ventralMuscleMaterial);
    }

    private void CreateSegmentedPhysics()
    {
        RemoveRootPhysicsBody();

        physicsRoot = new GameObject("Segmented Physics").transform;
        physicsRoot.SetParent(bodyRoot, false);
        segmentBodies = new Rigidbody[segmentCount];
        segmentColliders = new CapsuleCollider[segmentCount];
        segmentSpacing = bodyLength / Mathf.Max(1, segmentCount - 1);

        float segmentMass = Mathf.Max(0.0001f, rigidbodyMass) / segmentCount;
        for (int segment = 0; segment < segmentCount; segment++)
        {
            GameObject segmentObject = new GameObject($"Body Segment {segment:00}");
            segmentObject.transform.SetParent(physicsRoot, false);
            segmentObject.transform.localPosition = new Vector3(
                (segment / (float)(segmentCount - 1) - 0.5f) * bodyLength,
                0f,
                0f
            );

            Rigidbody rigidbody = segmentObject.AddComponent<Rigidbody>();
            rigidbody.mass = segmentMass;
            rigidbody.useGravity = useGravity;
            rigidbody.interpolation = RigidbodyInterpolation.Interpolate;
            rigidbody.collisionDetectionMode = CollisionDetectionMode.ContinuousSpeculative;
            rigidbody.constraints = freezePhysicsRotation
                ? RigidbodyConstraints.FreezeRotation
                : RigidbodyConstraints.None;

            CapsuleCollider collider = segmentObject.AddComponent<CapsuleCollider>();
            collider.direction = 0;
            collider.radius = bodyRadius * Mathf.Max(1f, colliderRadiusPadding);
            collider.height = Mathf.Max(segmentSpacing * 1.2f, collider.radius * 2f);

            if (showSegmentBodies)
            {
                MeshRenderer renderer = segmentObject.AddComponent<MeshRenderer>();
                MeshFilter filter = segmentObject.AddComponent<MeshFilter>();
                filter.sharedMesh = CreateDebugSegmentMesh();
                renderer.sharedMaterial = bodyMaterial;
            }

            segmentBodies[segment] = rigidbody;
            segmentColliders[segment] = collider;

            if (segment > 0)
            {
                ConfigureSegmentJoint(segmentObject, segmentBodies[segment - 1]);
            }
        }
    }

    private void ConfigureSegmentJoint(GameObject segmentObject, Rigidbody previousBody)
    {
        ConfigurableJoint joint = segmentObject.AddComponent<ConfigurableJoint>();
        joint.connectedBody = previousBody;
        joint.autoConfigureConnectedAnchor = false;
        joint.anchor = Vector3.left * segmentSpacing * 0.5f;
        joint.connectedAnchor = Vector3.right * segmentSpacing * 0.5f;
        joint.xMotion = ConfigurableJointMotion.Locked;
        joint.yMotion = ConfigurableJointMotion.Locked;
        joint.zMotion = ConfigurableJointMotion.Locked;
        joint.angularXMotion = ConfigurableJointMotion.Limited;
        joint.angularYMotion = ConfigurableJointMotion.Limited;
        joint.angularZMotion = ConfigurableJointMotion.Limited;
        joint.lowAngularXLimit = new SoftJointLimit { limit = -28f };
        joint.highAngularXLimit = new SoftJointLimit { limit = 28f };
        joint.angularYLimit = new SoftJointLimit { limit = 34f };
        joint.angularZLimit = new SoftJointLimit { limit = 34f };
        joint.enableCollision = false;
        joint.projectionMode = JointProjectionMode.PositionAndRotation;
        joint.projectionDistance = bodyRadius * 0.5f;
        joint.projectionAngle = 12f;
        joint.rotationDriveMode = RotationDriveMode.Slerp;
        joint.slerpDrive = new JointDrive
        {
            positionSpring = jointSpring,
            positionDamper = jointDamping,
            maximumForce = jointMaxForce,
        };
    }

    private void RemoveRootPhysicsBody()
    {
        CapsuleCollider rootCollider = GetComponent<CapsuleCollider>();
        if (rootCollider != null)
        {
            DestroyComponent(rootCollider);
        }

        Rigidbody rootBody = GetComponent<Rigidbody>();
        if (rootBody != null)
        {
            DestroyComponent(rootBody);
        }
    }

    private Mesh CreateDebugSegmentMesh()
    {
        GameObject primitive = GameObject.CreatePrimitive(PrimitiveType.Capsule);
        Mesh mesh = primitive.GetComponent<MeshFilter>().sharedMesh;
        DestroyComponent(primitive);
        return mesh;
    }

    private LineRenderer CreateMuscleBand(string objectName, Material material)
    {
        GameObject bandObject = new GameObject(objectName);
        bandObject.transform.SetParent(bodyRoot, false);

        LineRenderer line = bandObject.AddComponent<LineRenderer>();
        line.useWorldSpace = false;
        line.positionCount = segmentCount;
        line.startWidth = bodyRadius * 0.28f;
        line.endWidth = bodyRadius * 0.28f;
        line.sharedMaterial = material;
        return line;
    }

    private void BuildTriangles()
    {
        int triangleIndex = 0;
        for (int segment = 0; segment < segmentCount - 1; segment++)
        {
            for (int radial = 0; radial < radialResolution; radial++)
            {
                int nextRadial = (radial + 1) % radialResolution;
                int a = segment * radialResolution + radial;
                int b = segment * radialResolution + nextRadial;
                int c = (segment + 1) * radialResolution + radial;
                int d = (segment + 1) * radialResolution + nextRadial;

                triangles[triangleIndex++] = a;
                triangles[triangleIndex++] = c;
                triangles[triangleIndex++] = b;
                triangles[triangleIndex++] = b;
                triangles[triangleIndex++] = c;
                triangles[triangleIndex++] = d;
            }
        }
    }

    private void UpdateMuscleDrive(float deltaTime)
    {
        float decay = Mathf.Exp(-driveDecay * deltaTime);
        for (int i = 0; i < segmentCount; i++)
        {
            dorsalDrive[i] *= decay;
            ventralDrive[i] *= decay;
        }

        foreach (MuscleProjection projection in muscleProjections)
        {
            float state = simulator.GetState(projection.SourceId);
            float drive = (float)Math.Tanh(state) * projection.Sign * projection.Weight;
            int index = projection.SegmentIndex;

            if (projection.Side == MuscleSide.Dorsal)
            {
                dorsalDrive[index] += drive;
            }
            else
            {
                ventralDrive[index] += drive;
            }
        }

        SmoothDrive(dorsalDrive, smoothedDorsalDrive);
        SmoothDrive(ventralDrive, smoothedVentralDrive);
    }

    private void SmoothDrive(float[] source, float[] target)
    {
        for (int i = 0; i < source.Length; i++)
        {
            float total = source[i] * 0.5f;
            float weight = 0.5f;

            if (i > 0)
            {
                total += source[i - 1] * 0.25f;
                weight += 0.25f;
            }

            if (i + 1 < source.Length)
            {
                total += source[i + 1] * 0.25f;
                weight += 0.25f;
            }

            target[i] = Mathf.Clamp(total / weight, -1f, 1f);
        }
    }

    private void ApplyMuscleForces(float time)
    {
        for (int segment = 1; segment < segmentCount; segment++)
        {
            float fraction = segment / (float)(segmentCount - 1);
            float wave = Mathf.Sin((fraction * undulationCycles - time * undulationFrequency) * TwoPi);
            float baselineDrive = baselineUndulation <= 0f ? 0f : wave * baselineUndulation;
            float dorsal = Mathf.Max(0f, baselineDrive) + Mathf.Max(0f, smoothedDorsalDrive[segment]);
            float ventral = Mathf.Max(0f, -baselineDrive) + Mathf.Max(0f, smoothedVentralDrive[segment]);

            ApplyMusclePull(segment, 1f, dorsal);
            ApplyMusclePull(segment, -1f, ventral);
        }
    }

    private void ApplyMusclePull(int segment, float dorsalSign, float contraction)
    {
        if (contraction <= 0.0001f)
        {
            return;
        }

        Rigidbody current = segmentBodies[segment];
        Rigidbody previous = segmentBodies[segment - 1];
        Vector3 currentPoint = current.worldCenterOfMass + current.transform.up * (bodyRadius * dorsalSign);
        Vector3 previousPoint = previous.worldCenterOfMass + previous.transform.up * (bodyRadius * dorsalSign);
        Vector3 pull = previousPoint - currentPoint;
        float distance = pull.magnitude;
        if (distance <= 0.0001f)
        {
            return;
        }

        Vector3 force = pull / distance * (contraction * musclePullForce);
        current.AddForceAtPosition(force, currentPoint, ForceMode.Force);
        previous.AddForceAtPosition(-force, previousPoint, ForceMode.Force);
    }

    private void UpdateBodyMesh(float time)
    {
        for (int segment = 0; segment < segmentCount; segment++)
        {
            float fraction = segment / (float)(segmentCount - 1);
            float x = (fraction - 0.5f) * bodyLength;
            float wave = Mathf.Sin((fraction * undulationCycles - time * undulationFrequency) * TwoPi);
            float baselineDrive = baselineUndulation <= 0f ? 0f : wave * baselineUndulation;
            float dorsal = Mathf.Max(0f, baselineDrive) + Mathf.Max(0f, smoothedDorsalDrive[segment]);
            float ventral = Mathf.Max(0f, -baselineDrive) + Mathf.Max(0f, smoothedVentralDrive[segment]);
            float bend = baselineDrive + (dorsal - ventral) * neuralBendGain;

            Vector3 localUp = Vector3.up;
            Vector3 localRight = Vector3.forward;
            if (HasSegmentPhysics)
            {
                Transform segmentTransform = segmentBodies[segment].transform;
                centerline[segment] = BodyRootPoint(segmentTransform.position);
                localUp = BodyRootDirection(segmentTransform.up);
                localRight = BodyRootDirection(segmentTransform.forward);
            }
            else
            {
                centerline[segment] = new Vector3(x, bend, 0f);
            }

            float dorsalCompression = Mathf.Clamp01(dorsal * contractionScale);
            float ventralCompression = Mathf.Clamp01(ventral * contractionScale);

            for (int radial = 0; radial < radialResolution; radial++)
            {
                float angle = radial / (float)radialResolution * TwoPi;
                float vertical = Mathf.Cos(angle) * bodyRadius;
                float lateral = Mathf.Sin(angle) * bodyRadius * 0.78f;

                if (vertical > 0f)
                {
                    vertical *= 1f - dorsalCompression;
                }
                else
                {
                    vertical *= 1f - ventralCompression;
                }

                vertices[segment * radialResolution + radial] =
                    centerline[segment] + localUp * vertical + localRight * lateral;
            }

            dorsalBand.SetPosition(segment, centerline[segment] + localUp * bodyRadius);
            ventralBand.SetPosition(segment, centerline[segment] - localUp * bodyRadius);
        }

        bodyMesh.Clear();
        bodyMesh.vertices = vertices;
        bodyMesh.triangles = triangles;
        bodyMesh.RecalculateNormals();
        bodyMesh.RecalculateBounds();
    }

    private void EnsureMaterials()
    {
        if (bodyMaterial == null)
        {
            bodyMaterial = CreateMaterial(new Color(0.82f, 0.86f, 0.78f, 1f));
        }

        if (dorsalMuscleMaterial == null)
        {
            dorsalMuscleMaterial = CreateMaterial(new Color(0.95f, 0.38f, 0.28f, 1f));
        }

        if (ventralMuscleMaterial == null)
        {
            ventralMuscleMaterial = CreateMaterial(new Color(0.28f, 0.55f, 1f, 1f));
        }
    }

    private Material CreateMaterial(Color color)
    {
        Shader shader = Shader.Find("Universal Render Pipeline/Lit");
        if (shader == null)
        {
            shader = Shader.Find("Standard");
        }

        if (shader == null)
        {
            shader = Shader.Find("Sprites/Default");
        }

        Material material = new Material(shader);
        material.color = color;
        return material;
    }

    private Vector3 BodyRootPoint(Vector3 worldPoint)
    {
        return bodyRoot == null
            ? transform.InverseTransformPoint(worldPoint)
            : bodyRoot.InverseTransformPoint(worldPoint);
    }

    private Vector3 BodyRootDirection(Vector3 worldDirection)
    {
        Vector3 direction = bodyRoot == null
            ? transform.InverseTransformDirection(worldDirection)
            : bodyRoot.InverseTransformDirection(worldDirection);
        return direction.sqrMagnitude > 0.0001f ? direction.normalized : Vector3.up;
    }

    private void DestroyComponent(UnityEngine.Object component)
    {
        if (Application.isPlaying)
        {
            Destroy(component);
        }
        else
        {
            DestroyImmediate(component);
        }
    }

    private void Clear()
    {
        IsBuilt = false;

        if (bodyRoot == null)
        {
            return;
        }

        if (Application.isPlaying)
        {
            Destroy(bodyRoot.gameObject);
        }
        else
        {
            DestroyImmediate(bodyRoot.gameObject);
        }

        bodyRoot = null;
        physicsRoot = null;
        segmentBodies = new Rigidbody[0];
        segmentColliders = new CapsuleCollider[0];
    }
}
