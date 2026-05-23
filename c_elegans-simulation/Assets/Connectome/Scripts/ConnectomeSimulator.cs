using System;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
public sealed class ConnectomePayload
{
    public string schemaVersion;
    public ConnectomeSource source;
    public ConnectomeSummary summary;
    public ConnectomeValidation validation;
    public ConnectomeNode[] nodes;
    public ConnectomeEdge[] edges;
}

[Serializable]
public sealed class ConnectomeSource
{
    public string name;
    public string sourceFile;
    public string normalization;
    public string layout;
}

[Serializable]
public sealed class ConnectomeSummary
{
    public int rawRows;
    public int nodes;
    public int neurons;
    public int endOrgans;
    public int edges;
}

[Serializable]
public sealed class ConnectomeValidation
{
    public ChemicalMismatch[] chemicalMismatches;
    public ElectricalMismatch[] electricalMismatches;
    public MissingElectricalReciprocal[] missingElectricalReciprocals;
}

[Serializable]
public sealed class ChemicalMismatch
{
    public string source;
    public string target;
    public float sendWeight;
    public float receiveWeight;
}

[Serializable]
public sealed class ElectricalMismatch
{
    public string source;
    public string target;
    public float weight;
    public float reverseWeight;
}

[Serializable]
public sealed class MissingElectricalReciprocal
{
    public string source;
    public string target;
    public float weight;
}

[Serializable]
public sealed class ConnectomeNode
{
    public string id;
    public string kind;
    public string neuronClass;
    public string side;
    public int segment;
    public string cellType;
    public string cellCategory;
    public string notes;
    public string metadataSource;
    public float bodyFraction;
    public int index;
    public float x;
    public float y;
    public float z;
    public float fallbackX;
    public float fallbackY;
    public float fallbackZ;
}

[Serializable]
public sealed class ConnectomeEdge
{
    public string id;
    public string source;
    public string target;
    public string kind;
    public bool directed;
    public float weight;
    public int rowCount;
    public ConnectomeComponent[] components;
    public ConnectomeComponent[] receiveComponents;
}

[Serializable]
public sealed class ConnectomeComponent
{
    public string type;
    public float weight;
}

public sealed class ConnectomeSimulator : MonoBehaviour
{
    [Header("Data")]
    [SerializeField] private TextAsset connectomeJson;

    [Header("Dynamics")]
    [SerializeField] private float decay = 0.92f;
    [SerializeField] private float chemicalGain = 0.015f;
    [SerializeField] private float electricalGain = 0.03f;
    [SerializeField] private float neuromuscularGain = 0.02f;
    [SerializeField] private float activationLimit = 5f;

    public ConnectomePayload Payload { get; private set; }

    private readonly Dictionary<string, int> nodeIndexById = new Dictionary<string, int>();
    private float[] state = new float[0];
    private float[] nextState = new float[0];

    private void Awake()
    {
        Load();
    }

    private void Update()
    {
        Step(Time.deltaTime);
    }

    public void Load()
    {
        if (connectomeJson == null)
        {
            Debug.LogError("ConnectomeSimulator needs a Unity JSON TextAsset.");
            enabled = false;
            return;
        }

        Payload = JsonUtility.FromJson<ConnectomePayload>(connectomeJson.text);
        nodeIndexById.Clear();

        for (int i = 0; i < Payload.nodes.Length; i++)
        {
            nodeIndexById[Payload.nodes[i].id] = i;
        }

        state = new float[Payload.nodes.Length];
        nextState = new float[Payload.nodes.Length];

        Debug.Log($"Loaded connectome: {Payload.summary.nodes} nodes, {Payload.summary.edges} edges");
    }

    public void Stimulate(string nodeId, float amount)
    {
        if (nodeIndexById.TryGetValue(nodeId.ToUpperInvariant(), out int index))
        {
            state[index] = Mathf.Clamp(state[index] + amount, -activationLimit, activationLimit);
        }
    }

    public float GetState(string nodeId)
    {
        return nodeIndexById.TryGetValue(nodeId.ToUpperInvariant(), out int index) ? state[index] : 0f;
    }

    public void Step(float deltaTime)
    {
        if (Payload == null || Payload.edges == null)
        {
            return;
        }

        Array.Copy(state, nextState, state.Length);

        for (int i = 0; i < nextState.Length; i++)
        {
            nextState[i] *= Mathf.Pow(decay, deltaTime * 60f);
        }

        foreach (ConnectomeEdge edge in Payload.edges)
        {
            if (!nodeIndexById.TryGetValue(edge.source, out int sourceIndex))
            {
                continue;
            }

            if (!nodeIndexById.TryGetValue(edge.target, out int targetIndex))
            {
                continue;
            }

            if (edge.kind == "chemical")
            {
                nextState[targetIndex] += state[sourceIndex] * edge.weight * chemicalGain;
            }
            else if (edge.kind == "electrical")
            {
                float delta = state[sourceIndex] - state[targetIndex];
                float coupling = delta * edge.weight * electricalGain;
                nextState[sourceIndex] -= coupling;
                nextState[targetIndex] += coupling;
            }
            else if (edge.kind == "neuromuscular")
            {
                nextState[targetIndex] += state[sourceIndex] * edge.weight * neuromuscularGain;
            }
        }

        for (int i = 0; i < state.Length; i++)
        {
            state[i] = Mathf.Clamp(nextState[i], -activationLimit, activationLimit);
        }
    }
}
