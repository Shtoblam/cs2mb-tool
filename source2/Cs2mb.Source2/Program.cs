using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using ValveKeyValue;
using ValveResourceFormat;
using ValveResourceFormat.ResourceTypes;
using ValveResourceFormat.ResourceTypes.RubikonPhysics;
using ValveResourceFormat.Serialization.KeyValues;
using ValveResourceFormat.Utils;
using VrfResource = ValveResourceFormat.Resource;
using VrfHull = ValveResourceFormat.ResourceTypes.RubikonPhysics.Shapes.Hull;
using VrfMesh = ValveResourceFormat.ResourceTypes.RubikonPhysics.Shapes.Mesh;

internal static class Program
{
    private const string ToolVersion = "1.0.0";
    private const int MaxHullFaceEdges = 1024;

    private static int Main(string[] args)
    {
        if (args.Length == 0 || args[0] is "-h" or "--help" or "help")
        {
            PrintUsage();
            return args.Length == 0 ? 2 : 0;
        }

        try
        {
            return args[0] switch
            {
                "--version" or "version" => Version(),
                "inspect" => Inspect(args.Skip(1).ToArray()),
                "phys-summary" => PhysSummaryCommand(args.Skip(1).ToArray()),
                "phys" => Phys(args.Skip(1).ToArray()),
                "entities" => Entities(args.Skip(1).ToArray()),
                _ => Unknown(args[0]),
            };
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"cs2mb-source2: {error.GetType().Name}: {error.Message}");
            return 1;
        }
    }

    private static int Version()
    {
        Console.WriteLine($"cs2mb-source2 {ToolVersion}");
        return 0;
    }

    private static int Unknown(string command)
    {
        Console.Error.WriteLine($"cs2mb-source2: unknown command '{command}'");
        PrintUsage();
        return 2;
    }

    private static void PrintUsage()
    {
        Console.WriteLine("cs2mb-source2 - first-party Source 2 resource helper for CS2 Map Balance");
        Console.WriteLine();
        Console.WriteLine("Usage:");
        Console.WriteLine("  cs2mb-source2 inspect --input <resource>");
        Console.WriteLine("  cs2mb-source2 phys-summary --input <world_physics.vmdl_c>");
        Console.WriteLine("  cs2mb-source2 phys --input <world_physics.vmdl_c> --output <world_physics_physics.gltf>");
        Console.WriteLine("  cs2mb-source2 entities --input <default_ents.vents_c> --output <entities.txt>");
        Console.WriteLine();
        Console.WriteLine("All input files are read-only. The tool never writes to the game directory.");
    }

    private static string RequireOption(string[] args, string name)
    {
        for (var i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name)
            {
                return args[i + 1];
            }
        }
        throw new ArgumentException($"missing required option {name}");
    }

    private static VrfResource LoadResource(string path)
    {
        var full = Path.GetFullPath(path);
        if (!File.Exists(full))
        {
            throw new FileNotFoundException("resource not found", full);
        }
        var resource = new VrfResource();
        resource.Read(full);
        return resource;
    }

    private static int Inspect(string[] args)
    {
        var input = RequireOption(args, "--input");
        using var resource = LoadResource(input);
        Console.WriteLine($"file: {Path.GetFileName(input)}");
        Console.WriteLine($"header_version: {resource.HeaderVersion}");
        Console.WriteLine($"resource_version: {resource.Version}");
        Console.WriteLine($"resource_type: {resource.ResourceType}");
        Console.WriteLine($"file_size: {resource.FileSize}");
        Console.WriteLine($"blocks: {resource.Blocks.Count}");
        foreach (var block in resource.Blocks)
        {
            Console.WriteLine($"  {block.Type} offset={block.Offset} size={block.Size}");
        }
        return 0;
    }

    private static int PhysSummaryCommand(string[] args)
    {
        var input = RequireOption(args, "--input");
        using var resource = LoadResource(input);
        var phys = resource.GetBlockByType(BlockType.PHYS) as PhysAggregateData
            ?? throw new InvalidDataException("resource has no PHYS block");
        var summary = SummarizePhys(phys, input);
        Console.WriteLine(JsonSerializer.Serialize(summary, JsonOptions));
        return 0;
    }

    private static int Entities(string[] args)
    {
        var input = RequireOption(args, "--input");
        var output = RequireOption(args, "--output");
        using var resource = LoadResource(input);
        var lump = resource.GetBlockByType(BlockType.DATA) as EntityLump
            ?? throw new InvalidDataException("resource DATA block is not an entity lump");
        var entities = lump.GetEntities();
        var text = EntityDumpWriter.Write(lump, entities);
        var fullOutput = Path.GetFullPath(output);
        Directory.CreateDirectory(Path.GetDirectoryName(fullOutput)!);
        File.WriteAllText(fullOutput, text, new UTF8Encoding(false));
        Console.WriteLine($"wrote {fullOutput} ({text.Length} chars, {entities.Count} entities)");
        return 0;
    }

    private static int Phys(string[] args)
    {
        var input = RequireOption(args, "--input");
        var output = RequireOption(args, "--output");
        using var resource = LoadResource(input);
        var phys = resource.GetBlockByType(BlockType.PHYS) as PhysAggregateData
            ?? throw new InvalidDataException("resource has no PHYS block");
        var summary = SummarizePhys(phys, input);
        if (summary.Parts.Count == 0)
        {
            throw new InvalidDataException("PHYS block contains no parts");
        }

        var writer = new PhysicsGltfWriter(phys);
        var written = writer.Write(output);
        Console.WriteLine(
            $"wrote {written.GltfPath} and {written.BinPath} "
            + $"({written.Primitives} primitives, {written.Vertices} vertices, {written.Triangles} triangles)");
        Console.WriteLine(JsonSerializer.Serialize(summary, JsonOptions));
        return 0;
    }

    private sealed record ShapeCounts(int Meshes, int Hulls, int Spheres, int Capsules, long Vertices, long Triangles);
    private sealed record PartSummary(int Index, int CollisionAttributeIndex, int Meshes, int Hulls, int Spheres, int Capsules, long Vertices, long Triangles);
    private sealed record SurfaceSummary(int Index, string Name, string Hash);
    private sealed record CollisionAttributeSummary(int Index, string? Group, string[] InteractAs, string[] PhysicsTags);
    private sealed record PhysSummary(
        string Input,
        int PartsCount,
        ShapeCounts Totals,
        Vector3 BoundsMin,
        Vector3 BoundsMax,
        List<PartSummary> Parts,
        List<SurfaceSummary> Surfaces,
        List<CollisionAttributeSummary> CollisionAttributes);

    private static PhysSummary SummarizePhys(PhysAggregateData phys, string input)
    {
        var parts = new List<PartSummary>();
        var totals = new long[] { 0, 0, 0, 0, 0, 0 };
        var boundsMin = new Vector3(float.PositiveInfinity);
        var boundsMax = new Vector3(float.NegativeInfinity);
        var partIndex = 0;

        foreach (var part in phys.Parts)
        {
            var meshes = part.Shape.Meshes ?? Array.Empty<MeshDescriptor>();
            var hulls = part.Shape.Hulls ?? Array.Empty<HullDescriptor>();
            var spheres = part.Shape.Spheres ?? Array.Empty<SphereDescriptor>();
            var capsules = part.Shape.Capsules ?? Array.Empty<CapsuleDescriptor>();
            var vertices = 0L;
            var triangles = 0L;

            foreach (var descriptor in meshes)
            {
                var mesh = descriptor.Shape;
                var meshVertices = mesh.GetVertices();
                var meshTriangles = mesh.GetTriangles();
                vertices += meshVertices.Length;
                triangles += meshTriangles.Length;
                Expand(mesh.Min, ref boundsMin, ref boundsMax);
                Expand(mesh.Max, ref boundsMin, ref boundsMax);
            }
            foreach (var descriptor in hulls)
            {
                var hull = descriptor.Shape;
                var hullVertices = hull.GetVertexPositions();
                var hullFaces = hull.GetFaces();
                var hullEdges = hull.GetEdges();
                vertices += hullVertices.Length;
                foreach (var face in hullFaces)
                {
                    triangles += Math.Max(0, CountFaceVertices(hullEdges, face) - 2);
                }
                Expand(hull.Min, ref boundsMin, ref boundsMax);
                Expand(hull.Max, ref boundsMin, ref boundsMax);
            }

            foreach (var descriptor in spheres)
            {
                var center = descriptor.Shape.Center;
                var radius = descriptor.Shape.Radius;
                if (float.IsFinite(radius) && radius > 0f)
                {
                    var offset = new Vector3(radius);
                    Expand(center - offset, ref boundsMin, ref boundsMax);
                    Expand(center + offset, ref boundsMin, ref boundsMax);
                }
            }

            foreach (var descriptor in capsules)
            {
                var radius = descriptor.Shape.Radius;
                var centers = descriptor.Shape.Center;
                if (!float.IsFinite(radius) || radius <= 0f || centers == null)
                {
                    continue;
                }
                var offset = new Vector3(radius);
                foreach (var center in centers)
                {
                    Expand(center - offset, ref boundsMin, ref boundsMax);
                    Expand(center + offset, ref boundsMin, ref boundsMax);
                }
            }

            parts.Add(new PartSummary(partIndex++, part.CollisionAttributeIndex,
                meshes.Length, hulls.Length, spheres.Length, capsules.Length, vertices, triangles));
            totals[0] += meshes.Length;
            totals[1] += hulls.Length;
            totals[2] += spheres.Length;
            totals[3] += capsules.Length;
            totals[4] += vertices;
            totals[5] += triangles;
        }

        var surfaces = new List<SurfaceSummary>();
        var hashes = phys.SurfacePropertyHashes ?? Array.Empty<uint>();
        for (var i = 0; i < hashes.Length; i++)
        {
            var hash = hashes[i];
            var name = StringToken.GetKnownString(hash);
            surfaces.Add(new SurfaceSummary(i, name, $"{hash:x8}"));
        }

        var attributes = new List<CollisionAttributeSummary>();
        for (var i = 0; i < phys.CollisionAttributes.Count; i++)
        {
            var attribute = phys.CollisionAttributes[i];
            attributes.Add(new CollisionAttributeSummary(
                i,
                SafeString(attribute, "m_CollisionGroupString"),
                SafeArray(attribute, "m_InteractAsStrings", "m_PhysicsTagStrings"),
                SafeArray(attribute, "m_PhysicsTagStrings")));
        }

        if (!float.IsFinite(boundsMin.X))
        {
            boundsMin = Vector3.Zero;
            boundsMax = Vector3.Zero;
        }

        return new PhysSummary(input, parts.Count,
            new ShapeCounts((int)totals[0], (int)totals[1], (int)totals[2], (int)totals[3], totals[4], totals[5]),
            boundsMin, boundsMax, parts, surfaces, attributes);
    }

    private static string? SafeString(KVObject obj, string key)
    {
        try { return obj.GetStringProperty(key); }
        catch { return null; }
    }

    private static string[] SafeArray(KVObject obj, params string[] keys)
    {
        foreach (var key in keys)
        {
            try
            {
                var values = obj.GetArray<string>(key);
                if (values != null && values.Length > 0)
                {
                    return values;
                }
            }
            catch
            {
                // Try the next key.
            }
        }
        return Array.Empty<string>();
    }

    private static int CountFaceVertices(ReadOnlySpan<VrfHull.HalfEdge> edges, VrfHull.Face face)
    {
        var edge = face.Edge;
        var count = 0;
        do
        {
            if (edge < 0 || edge >= edges.Length || count > MaxHullFaceEdges)
            {
                return 0;
            }
            edge = edges[edge].Next;
            count++;
        } while (edge != face.Edge);
        return count;
    }

    private static void Expand(Vector3 point, ref Vector3 min, ref Vector3 max)
    {
        min = Vector3.Min(min, point);
        max = Vector3.Max(max, point);
    }

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        Converters = { new Vector3JsonConverter() },
    };

    private sealed class Vector3JsonConverter : JsonConverter<Vector3>
    {
        public override Vector3 Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
            => throw new NotSupportedException();
        public override void Write(Utf8JsonWriter writer, Vector3 value, JsonSerializerOptions options)
        {
            writer.WriteStartArray();
            writer.WriteNumberValue(MathF.Round(value.X, 6));
            writer.WriteNumberValue(MathF.Round(value.Y, 6));
            writer.WriteNumberValue(MathF.Round(value.Z, 6));
            writer.WriteEndArray();
        }
    }
}

/// <summary>
/// Writes the collision geometry as a glTF 2.0 triangle mesh set.
/// Positions are kept in Source/Hammer units and Source axes (x, y, z-up).
/// </summary>
internal sealed class PhysicsGltfWriter
{
    private const int MaxHullFaceEdges = 1024;
    private const int CurveSegments = 16;
    private const int SphereRings = 10;
    private const int CapsuleHemisphereRings = 5;
    private readonly PhysAggregateData phys;
    private readonly Dictionary<(int Collision, int Surface), PrimitiveGroup> groups = new();
    private readonly string[] surfaceNames;
    private readonly List<KVObject> attributes;

    public PhysicsGltfWriter(PhysAggregateData phys)
    {
        this.phys = phys;
        surfaceNames = new string[phys.SurfacePropertyHashes?.Length ?? 0];
        for (var i = 0; i < surfaceNames.Length; i++)
        {
            surfaceNames[i] = StringToken.GetKnownString(phys.SurfacePropertyHashes![i]);
        }
        attributes = phys.CollisionAttributes.ToList();
    }

    public sealed record WriteResult(string GltfPath, string BinPath, int Primitives, long Vertices, long Triangles);

    public WriteResult Write(string outputPath)
    {
        var gltfPath = Path.GetFullPath(outputPath);
        Directory.CreateDirectory(Path.GetDirectoryName(gltfPath)!);
        var stem = gltfPath.EndsWith("_physics.gltf", StringComparison.OrdinalIgnoreCase)
            ? gltfPath[..^".gltf".Length]
            : Path.Combine(Path.GetDirectoryName(gltfPath)!, Path.GetFileNameWithoutExtension(gltfPath) + "_physics");
        var binPath = stem + ".bin";

        var bindPose = phys.BindPose ?? Array.Empty<Matrix4x4>();
        for (var partIndex = 0; partIndex < phys.Parts.Length; partIndex++)
        {
            var part = phys.Parts[partIndex];
            var pose = partIndex < bindPose.Length ? bindPose[partIndex] : Matrix4x4.Identity;
            var partAttribute = part.CollisionAttributeIndex;

            foreach (var descriptor in part.Shape.Meshes ?? Array.Empty<MeshDescriptor>())
            {
                var group = GetGroup(
                    descriptor.CollisionAttributeIndex >= 0 ? descriptor.CollisionAttributeIndex : partAttribute,
                    descriptor.SurfacePropertyIndex);
                AddMesh(group, descriptor.Shape, pose);
            }

            foreach (var descriptor in part.Shape.Hulls ?? Array.Empty<HullDescriptor>())
            {
                var group = GetGroup(
                    descriptor.CollisionAttributeIndex >= 0 ? descriptor.CollisionAttributeIndex : partAttribute,
                    descriptor.SurfacePropertyIndex);
                AddHull(group, descriptor.Shape, pose);
            }

            foreach (var descriptor in part.Shape.Spheres ?? Array.Empty<SphereDescriptor>())
            {
                var group = GetGroup(
                    descriptor.CollisionAttributeIndex >= 0 ? descriptor.CollisionAttributeIndex : partAttribute,
                    descriptor.SurfacePropertyIndex);
                AddSphere(group, descriptor.Shape, pose);
            }

            foreach (var descriptor in part.Shape.Capsules ?? Array.Empty<CapsuleDescriptor>())
            {
                var group = GetGroup(
                    descriptor.CollisionAttributeIndex >= 0 ? descriptor.CollisionAttributeIndex : partAttribute,
                    descriptor.SurfacePropertyIndex);
                AddCapsule(group, descriptor.Shape, pose);
            }
        }

        var used = groups.Values.Where(g => g.Indices.Count > 0).OrderBy(g => g.Name, StringComparer.Ordinal).ToList();
        if (used.Count == 0)
        {
            throw new InvalidDataException("PHYS block produced no collision triangles");
        }

        var bin = new MemoryStream();
        var views = new List<BufferView>();
        var accessors = new List<Accessor>();
        var materials = new List<Material>();
        var meshes = new List<MeshDto>();
        var nodes = new List<NodeDto>();

        foreach (var group in used)
        {
            var positionOffset = (int)bin.Position;
            var min = new Vector3(float.PositiveInfinity);
            var max = new Vector3(float.NegativeInfinity);
            foreach (var vertex in group.Positions)
            {
                WriteSingle(bin, vertex.X);
                WriteSingle(bin, vertex.Y);
                WriteSingle(bin, vertex.Z);
                min = Vector3.Min(min, vertex);
                max = Vector3.Max(max, vertex);
            }
            var positionLength = (int)bin.Position - positionOffset;

            var indexOffset = (int)bin.Position;
            foreach (var index in group.Indices)
            {
                WriteUInt32(bin, index);
            }
            var indexLength = (int)bin.Position - indexOffset;

            var positionView = views.Count;
            views.Add(new BufferView(positionOffset, positionLength, 34962));
            var indexView = views.Count;
            views.Add(new BufferView(indexOffset, indexLength, 34963));

            var positionAccessor = accessors.Count;
            accessors.Add(new Accessor(positionView, 5126, group.Positions.Count, "VEC3",
                new[] { min.X, min.Y, min.Z }, new[] { max.X, max.Y, max.Z }));
            var indexAccessor = accessors.Count;
            accessors.Add(new Accessor(indexView, 5125, group.Indices.Count, "SCALAR", null, null));

            var materialIndex = materials.Count;
            materials.Add(new Material(group.Name));

            var meshIndex = meshes.Count;
            meshes.Add(new MeshDto(group.Name, new[] { new PrimitiveDto(
                new Dictionary<string, int> { ["POSITION"] = positionAccessor },
                indexAccessor,
                materialIndex) }));

            nodes.Add(new NodeDto(group.Name, meshIndex, new NodeExtras(
                group.SurfaceName,
                group.CollisionGroup,
                group.InteractAs)));
        }

        var bufferBytes = bin.ToArray();
        var gltf = new GltfDto(
            new AssetDto("2.0", "CS2 Map Balance internal Source 2 converter"),
            new[] { new BufferDto(bufferBytes.Length, Path.GetFileName(binPath)) },
            views,
            accessors,
            materials,
            meshes,
            nodes,
            new[] { new SceneDto(nodes.Select((_, i) => i).ToArray()) },
            0);

        File.WriteAllBytes(binPath, bufferBytes);
        var json = JsonSerializer.Serialize(gltf, GltfJsonOptions);
        File.WriteAllText(gltfPath, json, new UTF8Encoding(false));

        return new WriteResult(gltfPath, binPath, used.Count,
            used.Sum(g => (long)g.Positions.Count), used.Sum(g => (long)g.Indices.Count / 3));
    }

    private PrimitiveGroup GetGroup(int collisionAttributeIndex, int surfacePropertyIndex)
    {
        var key = (collisionAttributeIndex, surfacePropertyIndex);
        if (!groups.TryGetValue(key, out var group))
        {
            var surfaceName = surfacePropertyIndex >= 0 && surfacePropertyIndex < surfaceNames.Length
                ? surfaceNames[surfacePropertyIndex]
                : string.Empty;
            var attribute = collisionAttributeIndex >= 0 && collisionAttributeIndex < attributes.Count
                ? attributes[collisionAttributeIndex]
                : null;
            var tags = attribute == null
                ? Array.Empty<string>()
                : SafeArray(attribute, "m_InteractAsStrings", "m_PhysicsTagStrings");
            var groupName = attribute == null ? null : SafeString(attribute, "m_CollisionGroupString");
            var baseName = tags.Length > 0
                ? "physics_" + string.Join("_", tags)
                : (!string.IsNullOrEmpty(groupName) && !groupName.Equals("default", StringComparison.OrdinalIgnoreCase)
                    ? "physics_" + groupName
                    : "physics_group");
            var name = !string.IsNullOrEmpty(surfaceName) && !surfaceName.Equals("default", StringComparison.OrdinalIgnoreCase)
                ? $"{baseName}_{surfaceName}"
                : baseName;
            group = new PrimitiveGroup
            {
                Name = name,
                SurfaceName = surfaceName,
                CollisionGroup = groupName ?? "default",
                InteractAs = tags,
            };
            groups[key] = group;
        }
        return group;
    }

    private static void AddMesh(PrimitiveGroup group, VrfMesh mesh, Matrix4x4 pose)
    {
        var vertices = mesh.GetVertices();
        var triangles = mesh.GetTriangles();
        foreach (var triangle in triangles)
        {
            if (!ValidIndex(triangle.X, vertices.Length)
                || !ValidIndex(triangle.Y, vertices.Length)
                || !ValidIndex(triangle.Z, vertices.Length))
            {
                continue;
            }
            AddTriangle(group,
                Vector3.Transform(vertices[triangle.X], pose),
                Vector3.Transform(vertices[triangle.Y], pose),
                Vector3.Transform(vertices[triangle.Z], pose));
        }
    }

    private static void AddHull(PrimitiveGroup group, VrfHull hull, Matrix4x4 pose)
    {
        var vertices = hull.GetVertexPositions();
        var edges = hull.GetEdges();
        var faces = hull.GetFaces();
        foreach (var face in faces)
        {
            var faceVertices = new List<int>(16);
            var edge = face.Edge;
            var guard = 0;
            do
            {
                if (edge < 0 || edge >= edges.Length || guard++ > MaxHullFaceEdges)
                {
                    faceVertices.Clear();
                    break;
                }
                faceVertices.Add(edges[edge].Origin);
                edge = edges[edge].Next;
            } while (edge != face.Edge);

            if (faceVertices.Count < 3)
            {
                continue;
            }

            var first = faceVertices[0];
            if (!ValidIndex(first, vertices.Length))
            {
                continue;
            }
            var a = Vector3.Transform(vertices[first], pose);
            for (var i = 2; i < faceVertices.Count; i++)
            {
                var previous = faceVertices[i - 1];
                var current = faceVertices[i];
                if (!ValidIndex(previous, vertices.Length) || !ValidIndex(current, vertices.Length))
                {
                    continue;
                }
                AddTriangle(group, a,
                    Vector3.Transform(vertices[previous], pose),
                    Vector3.Transform(vertices[current], pose));
            }
        }
    }

    private static void AddSphere(PrimitiveGroup group, ValveResourceFormat.ResourceTypes.RubikonPhysics.Shapes.Sphere sphere, Matrix4x4 pose)
    {
        var radius = sphere.Radius;
        if (!IsFinite(sphere.Center) || !float.IsFinite(radius) || radius <= 0f)
        {
            throw new InvalidDataException("PHYS sphere has an invalid center or radius");
        }

        AddSphereAt(group, sphere.Center, radius, pose);
    }

    private static void AddSphereAt(PrimitiveGroup group, Vector3 center, float radius, Matrix4x4 pose)
    {
        var rings = new List<Vector3[]>(SphereRings + 1);
        for (var ring = 0; ring <= SphereRings; ring++)
        {
            var theta = MathF.PI * ring / SphereRings;
            var ringRadius = MathF.Sin(theta) * radius;
            var z = MathF.Cos(theta) * radius;
            var points = new Vector3[CurveSegments];
            for (var segment = 0; segment < CurveSegments; segment++)
            {
                var phi = 2f * MathF.PI * segment / CurveSegments;
                points[segment] = new Vector3(
                    center.X + MathF.Cos(phi) * ringRadius,
                    center.Y + MathF.Sin(phi) * ringRadius,
                    center.Z + z);
            }
            rings.Add(points);
        }

        AddCurvedSurface(group, rings, pose);
    }

    private static void AddCapsule(PrimitiveGroup group, ValveResourceFormat.ResourceTypes.RubikonPhysics.Shapes.Capsule capsule, Matrix4x4 pose)
    {
        var radius = capsule.Radius;
        var centers = capsule.Center;
        if (centers == null || centers.Length < 2 || !float.IsFinite(radius) || radius <= 0f)
        {
            throw new InvalidDataException("PHYS capsule has invalid centers or radius");
        }

        var start = centers[0];
        var end = centers[1];
        if (!IsFinite(start) || !IsFinite(end))
        {
            throw new InvalidDataException("PHYS capsule has a non-finite center");
        }

        var axis = end - start;
        var length = axis.Length();
        if (length < 1e-6f)
        {
            AddSphereAt(group, start, radius, pose);
            return;
        }
        axis /= length;

        var reference = MathF.Abs(axis.Z) > 0.99f ? Vector3.UnitX : Vector3.UnitZ;
        var u = Vector3.Normalize(Vector3.Cross(reference, axis));
        var v = Vector3.Cross(axis, u);

        var rings = new List<Vector3[]>(CapsuleHemisphereRings * 2 + 2);
        for (var ring = 0; ring <= CapsuleHemisphereRings; ring++)
        {
            var theta = MathF.PI * 0.5f * ring / CapsuleHemisphereRings;
            var ringRadius = MathF.Sin(theta) * radius;
            var center = start - axis * (MathF.Cos(theta) * radius);
            rings.Add(MakeRing(center, u, v, ringRadius));
        }

        rings.Add(MakeRing(end, u, v, radius));

        for (var ring = 1; ring <= CapsuleHemisphereRings; ring++)
        {
            var phi = MathF.PI * 0.5f * ring / CapsuleHemisphereRings;
            var center = end + axis * (MathF.Sin(phi) * radius);
            rings.Add(MakeRing(center, u, v, MathF.Cos(phi) * radius));
        }

        AddCurvedSurface(group, rings, pose);
    }

    private static Vector3[] MakeRing(Vector3 center, Vector3 u, Vector3 v, float radius)
    {
        var points = new Vector3[CurveSegments];
        for (var segment = 0; segment < CurveSegments; segment++)
        {
            var phi = 2f * MathF.PI * segment / CurveSegments;
            points[segment] = center + u * (MathF.Cos(phi) * radius) + v * (MathF.Sin(phi) * radius);
        }
        return points;
    }

    private static void AddCurvedSurface(PrimitiveGroup group, List<Vector3[]> rings, Matrix4x4 pose)
    {
        for (var ring = 0; ring < rings.Count - 1; ring++)
        {
            var current = rings[ring];
            var next = rings[ring + 1];
            for (var segment = 0; segment < CurveSegments; segment++)
            {
                var nextSegment = (segment + 1) % CurveSegments;
                var a = Vector3.Transform(current[segment], pose);
                var b = Vector3.Transform(current[nextSegment], pose);
                var c = Vector3.Transform(next[segment], pose);
                var d = Vector3.Transform(next[nextSegment], pose);
                AddTriangle(group, a, c, b);
                AddTriangle(group, b, c, d);
            }
        }
    }

    private static void AddTriangle(PrimitiveGroup group, Vector3 a, Vector3 b, Vector3 c)
    {
        if (!IsFinite(a) || !IsFinite(b) || !IsFinite(c))
        {
            return;
        }
        if (Vector3.DistanceSquared(a, b) < 1e-12f
            || Vector3.DistanceSquared(b, c) < 1e-12f
            || Vector3.DistanceSquared(c, a) < 1e-12f)
        {
            return;
        }
        var baseIndex = (uint)group.Positions.Count;
        group.Positions.Add(a);
        group.Positions.Add(b);
        group.Positions.Add(c);
        group.Indices.Add(baseIndex);
        group.Indices.Add(baseIndex + 1);
        group.Indices.Add(baseIndex + 2);
    }

    private static bool ValidIndex(int index, int length) => index >= 0 && index < length;

    private static bool IsFinite(Vector3 value)
        => float.IsFinite(value.X) && float.IsFinite(value.Y) && float.IsFinite(value.Z);

    private static string[] SafeArray(KVObject obj, params string[] keys)
    {
        foreach (var key in keys)
        {
            try
            {
                var values = obj.GetArray<string>(key);
                if (values != null && values.Length > 0)
                {
                    return values;
                }
            }
            catch
            {
                // Try the next key.
            }
        }
        return Array.Empty<string>();
    }

    private static string? SafeString(KVObject obj, string key)
    {
        try { return obj.GetStringProperty(key); }
        catch { return null; }
    }

    private static void WriteSingle(Stream stream, float value)
    {
        Span<byte> data = stackalloc byte[4];
        BitConverter.TryWriteBytes(data, value);
        stream.Write(data);
    }

    private static void WriteUInt32(Stream stream, uint value)
    {
        Span<byte> data = stackalloc byte[4];
        BitConverter.TryWriteBytes(data, value);
        stream.Write(data);
    }

    private sealed class PrimitiveGroup
    {
        public string Name = string.Empty;
        public string SurfaceName = string.Empty;
        public string CollisionGroup = "default";
        public string[] InteractAs = Array.Empty<string>();
        public List<Vector3> Positions { get; } = new();
        public List<uint> Indices { get; } = new();
    }

    private static readonly JsonSerializerOptions GltfJsonOptions = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private sealed record GltfDto(
        AssetDto Asset,
        BufferDto[] Buffers,
        List<BufferView> BufferViews,
        List<Accessor> Accessors,
        List<Material> Materials,
        List<MeshDto> Meshes,
        List<NodeDto> Nodes,
        SceneDto[] Scenes,
        int Scene);
    private sealed record AssetDto(string Version, string Generator);
    private sealed record BufferDto(int ByteLength, string Uri);
    private sealed record BufferView(int ByteOffset, int ByteLength, int Target);
    private sealed record Accessor(int BufferView, int ComponentType, int Count, string Type, float[]? Min, float[]? Max);
    private sealed record Material(string Name);
    private sealed record MeshDto(string Name, PrimitiveDto[] Primitives);
    private sealed record PrimitiveDto(Dictionary<string, int> Attributes, int Indices, int Material);
    private sealed record NodeDto(string Name, int Mesh, NodeExtras Extras);
    private sealed record NodeExtras(
        [property: JsonPropertyName("SurfaceProperty")] string SurfaceProperty,
        [property: JsonPropertyName("CollisionGroup")] string CollisionGroup,
        [property: JsonPropertyName("InteractAs")] string[] InteractAs);
    private sealed record SceneDto(int[] Nodes);
}

internal static class EntityDumpWriter
{
    public static string Write(EntityLump lump, List<EntityLump.Entity> entities)
    {
        var builder = new StringBuilder();
        for (var index = 0; index < entities.Count; index++)
        {
            var entity = entities[index];
            builder.Append("====").Append(index.ToString(CultureInfo.InvariantCulture)).AppendLine("====");

            var ordered = OrderProperties(entity);
            foreach (var property in ordered)
            {
                var value = EntityLump.StringifyValue(property.Value);
                builder.Append(property.Key.PadRight(30)).Append(" = ").AppendLine(value);
            }

            if (entity.Connections != null)
            {
                foreach (var connection in entity.Connections)
                {
                    builder.Append('@').Append(connection.OutputName).Append(' ');
                    if (connection.Delay > 0)
                    {
                        builder.Append("Delay=").Append(connection.Delay.ToString(CultureInfo.InvariantCulture)).Append(' ');
                    }
                    if (connection.TimesToFire == 1)
                    {
                        builder.Append("OnlyOnce ");
                    }
                    else if (connection.TimesToFire >= 2)
                    {
                        builder.Append("Only").Append(connection.TimesToFire.ToString(CultureInfo.InvariantCulture)).Append("Times ");
                    }
                    builder.Append(connection.InputName).Append(' ').Append(connection.TargetName);
                    if (!string.IsNullOrEmpty(connection.OverrideParam) && connection.OverrideParam != "(null)")
                    {
                        builder.Append(' ').Append(connection.OverrideParam);
                    }
                    builder.AppendLine();
                }
            }

            builder.AppendLine();
        }
        return builder.ToString();
    }

    private static List<KeyValuePair<string, KVObject>> OrderProperties(EntityLump.Entity entity)
    {
        var properties = entity.Children.ToList();
        var ordered = new List<KeyValuePair<string, KVObject>>(properties.Count);
        AddFirst(ordered, properties, "classname");
        AddFirst(ordered, properties, "targetname");
        AddFirst(ordered, properties, "place_name");
        AddFirst(ordered, properties, "origin");
        ordered.AddRange(properties);
        return ordered;
    }

    private static void AddFirst(List<KeyValuePair<string, KVObject>> target, List<KeyValuePair<string, KVObject>> source, string key)
    {
        for (var i = 0; i < source.Count; i++)
        {
            if (source[i].Key.Equals(key, StringComparison.OrdinalIgnoreCase))
            {
                target.Add(source[i]);
                source.RemoveAt(i);
                return;
            }
        }
    }
}
