using System;
using System.Collections.Generic;
using UnityEngine;

public sealed class ConnectomeDemoStimulus : MonoBehaviour
{
    [SerializeField] private ConnectomeSimulator simulator;
    [SerializeField] private bool stimulateOnPlay = true;
    [SerializeField] private float sampleInterval = 0.12f;
    [SerializeField] private float activationProbability = 0.18f;
    [SerializeField] private float minimumStimulus = 0.02f;
    [SerializeField] private float maximumStimulus = 0.28f;
    [SerializeField] private bool allowNegativeStimuli;
    [SerializeField] private int randomSeed;

    private readonly List<string> inputNeuronIds = new List<string>();
    private System.Random random;
    private float nextSampleTime;

    private void Awake()
    {
        if (simulator == null)
        {
            simulator = GetComponent<ConnectomeSimulator>();
        }

        random = new System.Random(randomSeed == 0 ? Environment.TickCount : randomSeed);
    }

    private void Start()
    {
        EnsureInputNeurons();
    }

    private void Update()
    {
        if (!stimulateOnPlay || simulator == null || simulator.Payload == null)
        {
            return;
        }

        EnsureInputNeurons();
        if (Time.time < nextSampleTime)
        {
            return;
        }

        nextSampleTime = Time.time + Mathf.Max(0.01f, sampleInterval);
        ApplyUniformRandomStimuli();
    }

    private void EnsureInputNeurons()
    {
        if (inputNeuronIds.Count > 0)
        {
            return;
        }

        if (simulator.Payload == null)
        {
            simulator.Load();
        }

        if (simulator.Payload == null || simulator.Payload.nodes == null)
        {
            return;
        }

        foreach (ConnectomeNode node in simulator.Payload.nodes)
        {
            if (IsInputNeuron(node))
            {
                inputNeuronIds.Add(node.id);
            }
        }

        Debug.Log($"Uniform random stimulus targeting {inputNeuronIds.Count} sensory input neurons.");
    }

    private bool IsInputNeuron(ConnectomeNode node)
    {
        if (node.kind != "neuron")
        {
            return false;
        }

        if (string.Equals(node.cellType, "sensory", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return !string.IsNullOrEmpty(node.cellCategory)
            && node.cellCategory.StartsWith("SN", StringComparison.OrdinalIgnoreCase);
    }

    private void ApplyUniformRandomStimuli()
    {
        if (inputNeuronIds.Count == 0)
        {
            return;
        }

        float low = Mathf.Min(minimumStimulus, maximumStimulus);
        float high = Mathf.Max(minimumStimulus, maximumStimulus);
        float probability = Mathf.Clamp01(activationProbability);

        foreach (string neuronId in inputNeuronIds)
        {
            if (random.NextDouble() > probability)
            {
                continue;
            }

            float value = Uniform(low, high);
            if (allowNegativeStimuli && random.NextDouble() < 0.5)
            {
                value = -value;
            }

            simulator.Stimulate(neuronId, value);
        }
    }

    private float Uniform(float minimum, float maximum)
    {
        return minimum + (maximum - minimum) * (float)random.NextDouble();
    }
}
