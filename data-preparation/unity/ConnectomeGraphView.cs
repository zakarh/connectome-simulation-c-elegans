using System.Collections.Generic;
using UnityEngine;

public sealed class ConnectomeGraphView : MonoBehaviour
{
    [SerializeField] private ConnectomeSimulator simulator;
    [SerializeField] private NematodeBodyController body;
    [SerializeField] private bool buildOnStart = true;
    [SerializeField] private bool drawEdges = true;
    [SerializeField] private bool followBodyPose = true;
    [SerializeField] private float nodeScale = 0.08f;
    [SerializeField] private float lineWidth = 0.01f;
    [SerializeField] private Material neuronMaterial;
    [SerializeField] private Material outputMaterial;
    [SerializeField] private Material chemicalMaterial;
    [SerializeField] private Material electricalMaterial;
    [SerializeField] private Material neuromuscularMaterial;

    private readonly Dictionary<string, Transform> nodeViews = new Dictionary<string, Transform>();
    private readonly List<EdgeView> edgeViews = new List<EdgeView>();
    private Transform graphRoot;

    private struct EdgeView
    {
        public LineRenderer Line;
        public Transform Source;
        public Transform Target;
    }

    private void Start()
    {
        if (buildOnStart)
        {
            Rebuild();
        }
    }

    private void Update()
    {
        if (simulator == null || simulator.Payload == null)
        {
            return;
        }

        foreach (ConnectomeNode node in simulator.Payload.nodes)
        {
            if (!nodeViews.TryGetValue(node.id, out Transform view))
            {
                continue;
            }

            view.localPosition = NodePosition(node);
            float activity = Mathf.Abs(simulator.GetState(node.id));
            float scale = nodeScale * (1f + activity * 0.25f);
            view.localScale = Vector3.one * scale;
        }

        foreach (EdgeView edgeView in edgeViews)
        {
            edgeView.Line.SetPosition(0, edgeView.Source.localPosition);
            edgeView.Line.SetPosition(1, edgeView.Target.localPosition);
        }
    }

    public void Rebuild()
    {
        if (simulator == null)
        {
            simulator = GetComponent<ConnectomeSimulator>();
        }

        if (body == null)
        {
            body = GetComponent<NematodeBodyController>();
        }

        if (simulator == null)
        {
            Debug.LogError("ConnectomeGraphView needs a ConnectomeSimulator.");
            return;
        }

        if (simulator.Payload == null)
        {
            simulator.Load();
        }

        Clear();
        EnsureMaterials();

        graphRoot = new GameObject("Connectome Graph").transform;
        graphRoot.SetParent(transform, false);

        foreach (ConnectomeNode node in simulator.Payload.nodes)
        {
            CreateNode(node);
        }

        if (drawEdges)
        {
            foreach (ConnectomeEdge edge in simulator.Payload.edges)
            {
                CreateEdge(edge);
            }
        }
    }

    private void CreateNode(ConnectomeNode node)
    {
        GameObject nodeObject = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        nodeObject.name = node.id;
        nodeObject.transform.SetParent(graphRoot, false);
        nodeObject.transform.localPosition = NodePosition(node);
        nodeObject.transform.localScale = Vector3.one * nodeScale;

        MeshRenderer renderer = nodeObject.GetComponent<MeshRenderer>();
        renderer.sharedMaterial = node.kind == "neuron" ? neuronMaterial : outputMaterial;
        nodeViews[node.id] = nodeObject.transform;
    }

    private void CreateEdge(ConnectomeEdge edge)
    {
        if (!nodeViews.TryGetValue(edge.source, out Transform source))
        {
            return;
        }

        if (!nodeViews.TryGetValue(edge.target, out Transform target))
        {
            return;
        }

        GameObject edgeObject = new GameObject(edge.id);
        edgeObject.transform.SetParent(graphRoot, false);

        LineRenderer line = edgeObject.AddComponent<LineRenderer>();
        line.useWorldSpace = false;
        line.positionCount = 2;
        line.SetPosition(0, source.localPosition);
        line.SetPosition(1, target.localPosition);
        line.startWidth = Mathf.Clamp(lineWidth * Mathf.Sqrt(edge.weight), lineWidth, lineWidth * 5f);
        line.endWidth = line.startWidth;
        line.sharedMaterial = MaterialForEdge(edge.kind);

        edgeViews.Add(
            new EdgeView
            {
                Line = line,
                Source = source,
                Target = target,
            }
        );
    }

    private Vector3 NodePosition(ConnectomeNode node)
    {
        if (followBodyPose && body != null && body.IsBuilt)
        {
            return body.GetBodySpacePosition(node.bodyFraction, node.y, node.z);
        }

        return new Vector3(node.x, node.y, node.z);
    }

    private Material MaterialForEdge(string kind)
    {
        if (kind == "chemical")
        {
            return chemicalMaterial;
        }

        if (kind == "electrical")
        {
            return electricalMaterial;
        }

        return neuromuscularMaterial;
    }

    private void EnsureMaterials()
    {
        if (neuronMaterial == null)
        {
            neuronMaterial = CreateMaterial(new Color(0.25f, 0.72f, 1f, 1f));
        }

        if (outputMaterial == null)
        {
            outputMaterial = CreateMaterial(new Color(1f, 0.67f, 0.22f, 1f));
        }

        if (chemicalMaterial == null)
        {
            chemicalMaterial = CreateMaterial(new Color(1f, 0.32f, 0.28f, 0.24f));
        }

        if (electricalMaterial == null)
        {
            electricalMaterial = CreateMaterial(new Color(0.25f, 0.62f, 1f, 0.32f));
        }

        if (neuromuscularMaterial == null)
        {
            neuromuscularMaterial = CreateMaterial(new Color(0.35f, 0.9f, 0.45f, 0.35f));
        }
    }

    private Material CreateMaterial(Color color)
    {
        Shader shader = Shader.Find("Sprites/Default");
        Material material = new Material(shader);
        material.color = color;
        return material;
    }

    private void Clear()
    {
        nodeViews.Clear();
        edgeViews.Clear();

        if (graphRoot == null)
        {
            return;
        }

        if (Application.isPlaying)
        {
            Destroy(graphRoot.gameObject);
        }
        else
        {
            DestroyImmediate(graphRoot.gameObject);
        }
    }
}
