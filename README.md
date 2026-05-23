# Connectome Simulation C. Elegans

This project converts WormAtlas/WormWiring C. elegans connectome data into SQLite and Unity JSON, then uses it to drive a Unity simulation of a nematode-like body. The Unity model includes neuron nodes, chemical synapse edges, electrical junctions, random sensory input, body-axis neuron placement, and a segmented rigidbody chain whose dorsal and ventral muscle forces are approximated from neuromuscular connectivity.

![Demo Video](https://youtu.be/GIpXY_iIChA)

## C. elegans Connectome Pipeline

This folder prepares the WormAtlas/WormWiring connectome data for the Unity project in `../c_elegans-simulation`.

The current Unity model has:

- one simulated node per exported neuron/end-organ node,
- directed chemical synapse edges,
- undirected electrical junction edges,
- neuromuscular edges mapped onto a segmented physics body,
- body-axis neuron placement enriched with WormWiring SI 4 cell metadata,
- uniform-random sensory input stimuli,
- a segmented rigidbody body with jointed sections and muscle pull forces.

## Files

- `import_connectome.py`: converts the CSV connectome into SQLite and Unity JSON.
- `data/NeuronConnect.csv`: CSV export of the legacy WormAtlas `NeuronConnect.xls`.
- `data/wormwiring/si4_sheets/*.csv`: WormWiring SI 4 cell list sheets exported to CSV.
- `data/connectome.db`: normalized SQLite graph output.
- `data/unity_connectome.json`: Unity JSON export. This is body-axis enriched by default.
- `data/unity_connectome_body.json`: explicit body-axis JSON copy.
- `unity/*.cs`: mirrored Unity scripts used by the Unity project.

The live Unity copies are in:

```text
../c_elegans-simulation/Assets/Connectome/Scripts
../c_elegans-simulation/Assets/Connectome/Data
```

## Rebuild Data

Run from this `data-preparation` folder:

```powershell
python import_connectome.py
```

That writes:

```text
data/connectome.db
data/unity_connectome.json
```

To also write the explicit body-layout filename:

```powershell
python import_connectome.py --json data\unity_connectome_body.json
```

After rebuilding, copy the JSON into the Unity project:

```powershell
Copy-Item data\unity_connectome.json ..\c_elegans-simulation\Assets\Connectome\Data\unity_connectome.json -Force
```

## Connection Mapping

- `S` and `Sp` rows become directed chemical edges from `Neuron 1` to `Neuron 2`.
- `R` and `Rp` rows are reversed and used to validate the chemical send rows.
- `EJ` rows are reciprocal in the source table and are collapsed into one undirected electrical edge.
- `NMJ` rows become directed neuromuscular edges to the aggregate `NMJ` output node.

Current generated counts:

```text
raw rows: 6417
nodes: 281
neurons: 280
edges: 2826
chemical edges: 2194
electrical edges: 517
neuromuscular edges: 115
```

## Body Layout

The JSON includes body-axis coordinates and metadata fields such as `cellType`, `cellCategory`, `bodyFraction`, and `metadataSource`.

These positions are not measured 3D nuclei coordinates. They are an anatomical approximation built from:

- WormWiring SI 4 cell type/category metadata,
- neuron class names,
- segment numbers such as `VA01`, `VB11`, `VD13`,
- left/right/dorsal/ventral suffixes,
- known head, ventral-cord, and tail class groupings.

## Unity Components

Use one scene object, currently named `C Elegans Connectome`, with these components:

- `ConnectomeSimulator`: loads the JSON and steps neuron state.
- `NematodeBodyController`: builds the generated body mesh and segmented physics chain.
- `ConnectomeGraphView`: places neuron spheres along the body and updates them as the body moves.
- `ConnectomeDemoStimulus`: applies uniform-random stimulus values to sensory neurons.

`SampleScene` is already configured with these components.

## Stimulus

`ConnectomeDemoStimulus` targets sensory input neurons using WormWiring metadata:

```text
cellType == sensory
or cellCategory starts with SN
```

Default script values:

```text
Sample Interval: 0.12
Activation Probability: 0.18
Minimum Stimulus: 0.02
Maximum Stimulus: 0.28
Allow Negative Stimuli: false
```

The scene may override those serialized values in the inspector.

## Physics And Muscles

`NematodeBodyController` builds one `Rigidbody` and `CapsuleCollider` per body segment. Adjacent segment bodies are connected with `ConfigurableJoint`s.

Muscle drive is derived from neuromuscular edges:

- dorsal motor classes pull the dorsal side of matching segment bodies,
- ventral motor classes pull the ventral side of matching segment bodies,
- DD/VD classes are treated as inhibitory sign flips,
- forces are applied with `AddForceAtPosition` to neighboring segment rigidbodies.

Gravity is enabled by default. `Baseline Undulation` is `0`, so there is no scripted swimming motion unless you explicitly raise it for debugging.

Important limitation: the current `NeuronConnect` source has an aggregate `NMJ` target, not one target per individual body-wall muscle cell. The rigidbody muscle mapping therefore uses motor neuron class and segment as an approximation.

## Verification

The Unity C# project has been checked with:

```powershell
dotnet build ..\c_elegans-simulation\c_elegans-simulation.sln --no-restore
```

Expected result:

```text
Build succeeded.
0 Warning(s)
0 Error(s)
```
