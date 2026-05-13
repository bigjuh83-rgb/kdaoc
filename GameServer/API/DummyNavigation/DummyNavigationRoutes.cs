using System;
using System.Buffers;
using System.Linq;
using System.Numerics;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;

namespace DOL.GS.API.DummyNavigation
{
    internal static class DummyNavigationRoutes
    {
        private const int DefaultMaxNodes = 128;
        private const int HardMaxNodes = 512;
        private const int InternalPathNodeBufferSize = 256;
        private const float DefaultSnapRange = 64f;
        private const float FloorSearchDepth = 256f;

        public static void MapDummyNavigationRoutes(this WebApplication api)
        {
            api.MapGet("/api/dummy/nav/path", (HttpContext context) =>
            {
                NavigationRequest request = NavigationRequest.From(context);
                NavigationResponse response = BuildPathResponse(request);

                return response.Status == "InvalidRequest" ? Results.BadRequest(response) : Results.Ok(response);
            });
        }

        private static NavigationResponse BuildPathResponse(NavigationRequest request)
        {
            if (!request.IsValid)
                return NavigationResponse.Fail("InvalidRequest", request.Error);

            Region region = WorldMgr.GetRegion((ushort)request.Region);

            if (region == null)
                return NavigationResponse.Fail("RegionNotFound", $"Region {request.Region} was not found.", request.Region);

            Zone startZone = request.Zone > 0 ? WorldMgr.GetZone((ushort)request.Zone) : region.GetZone(request.StartX, request.StartY);

            if (startZone == null)
                return NavigationResponse.Fail("ZoneNotFound", "Start location is outside a known zone.", request.Region);

            Zone endZone = region.GetZone(request.EndX, request.EndY);

            if (endZone == null)
                return NavigationResponse.Fail("ZoneNotFound", "End location is outside a known zone.", request.Region);

            if (startZone.ID != endZone.ID)
                return NavigationResponse.Fail("CrossZonePathUnsupported", "Start and end locations must be inside the same zone.", request.Region, startZone.ID);

            bool navmeshAvailable = startZone.IsPathfindingEnabled && PathfindingProvider.Instance.HasNavmesh(startZone);

            if (!navmeshAvailable)
                return NavigationResponse.Fail("NavmeshUnavailable", "No navmesh is loaded for this zone.", request.Region, startZone.ID, false);

            Vector3 start = new(request.StartX, request.StartY, request.StartZ);
            Vector3 end = new(request.EndX, request.EndY, request.EndZ);

            if (request.Snap)
            {
                PathfindingProvider.Instance.TrySnapToMesh(startZone, ref start, request.SnapRange);
                PathfindingProvider.Instance.TrySnapToMesh(startZone, ref end, request.SnapRange);
            }

            EDtPolyFlags[] filters = request.AvoidBlockingDoors
                ? PathfindingProvider.Instance.BlockingDoorAvoidanceFilters
                : PathfindingProvider.Instance.DefaultFilters;

            int queryNodeCapacity = Math.Min(HardMaxNodes, Math.Max(request.MaxNodes, InternalPathNodeBufferSize));
            WrappedPathfindingNode[] rentedNodes = ArrayPool<WrappedPathfindingNode>.Shared.Rent(queryNodeCapacity);

            try
            {
                PathfindingResult result = PathfindingProvider.Instance.GetPathStraight(
                    startZone,
                    start,
                    end,
                    filters,
                    rentedNodes.AsSpan(0, queryNodeCapacity));
                int nodeCount = Math.Min(result.NodeCount, Math.Min(request.MaxNodes, queryNodeCapacity));
                NavigationPoint[] points = new NavigationPoint[nodeCount];

                for (int i = 0; i < nodeCount; i++)
                {
                    WrappedPathfindingNode node = rentedNodes[i];
                    points[i] = new NavigationPoint(
                        (int)Math.Round(node.Position.X),
                        (int)Math.Round(node.Position.Y),
                        (int)Math.Round(node.Position.Z),
                        node.Flags.ToString());
                }

                Vector3? floor = PathfindingProvider.Instance.GetFloorBeneath(startZone, start, FloorSearchDepth, filters);
                bool lineOfSight = PathfindingProvider.Instance.HasLineOfSight(startZone, start, end, filters);
                bool ok = result.Status is PathfindingStatus.PathFound or PathfindingStatus.PartialPathFound or PathfindingStatus.BufferTooSmall;

                return new NavigationResponse(
                    Ok: ok,
                    Status: result.Status.ToString(),
                    Error: ok ? string.Empty : "Pathfinding did not find a traversable path.",
                    Region: request.Region,
                    Zone: startZone.ID,
                    NavmeshAvailable: true,
                    LineOfSight: lineOfSight,
                    SnappedStart: NavigationPoint.FromVector(start),
                    SnappedEnd: NavigationPoint.FromVector(end),
                    Floor: floor.HasValue ? NavigationPoint.FromVector(floor.Value) : null,
                    Points: points);
            }
            finally
            {
                ArrayPool<WrappedPathfindingNode>.Shared.Return(rentedNodes);
            }
        }

        private readonly record struct NavigationRequest(
            int Region,
            int Zone,
            int StartX,
            int StartY,
            int StartZ,
            int EndX,
            int EndY,
            int EndZ,
            int MaxNodes,
            float SnapRange,
            bool Snap,
            bool AvoidBlockingDoors,
            bool IsValid,
            string Error)
        {
            public static NavigationRequest From(HttpContext context)
            {
                IQueryCollection query = context.Request.Query;

                if (!ReadInt(query, "region", out int region) || region <= 0)
                    return Invalid("region is required.");

                if (!ReadInt(query, "startX", out int startX) ||
                    !ReadInt(query, "startY", out int startY) ||
                    !ReadInt(query, "startZ", out int startZ) ||
                    !ReadInt(query, "endX", out int endX) ||
                    !ReadInt(query, "endY", out int endY) ||
                    !ReadInt(query, "endZ", out int endZ))
                    return Invalid("startX/startY/startZ/endX/endY/endZ are required.");

                int zone = ReadInt(query, "zone", out int rawZone) ? Math.Max(0, rawZone) : 0;
                int maxNodes = ReadInt(query, "maxNodes", out int rawMaxNodes)
                    ? Math.Clamp(rawMaxNodes, 2, HardMaxNodes)
                    : DefaultMaxNodes;
                float snapRange = ReadFloat(query, "snapRange", out float rawSnapRange)
                    ? Math.Clamp(rawSnapRange, 1f, 1024f)
                    : DefaultSnapRange;
                bool snap = !ReadBool(query, "snap", out bool rawSnap) || rawSnap;
                bool avoidBlockingDoors = !ReadBool(query, "avoidBlockingDoors", out bool rawAvoidBlockingDoors) || rawAvoidBlockingDoors;

                return new(region, zone, startX, startY, startZ, endX, endY, endZ, maxNodes, snapRange, snap, avoidBlockingDoors, true, string.Empty);
            }

            private static NavigationRequest Invalid(string error)
            {
                return new(0, 0, 0, 0, 0, 0, 0, 0, DefaultMaxNodes, DefaultSnapRange, true, true, false, error);
            }

            private static bool ReadInt(IQueryCollection query, string key, out int value)
            {
                return int.TryParse(query[key].FirstOrDefault(), out value);
            }

            private static bool ReadFloat(IQueryCollection query, string key, out float value)
            {
                return float.TryParse(query[key].FirstOrDefault(), out value);
            }

            private static bool ReadBool(IQueryCollection query, string key, out bool value)
            {
                return bool.TryParse(query[key].FirstOrDefault(), out value);
            }
        }

        private readonly record struct NavigationPoint(int X, int Y, int Z, string Flags = "")
        {
            public static NavigationPoint FromVector(Vector3 point)
            {
                return new(
                    (int)Math.Round(point.X),
                    (int)Math.Round(point.Y),
                    (int)Math.Round(point.Z));
            }
        }

        private readonly record struct NavigationResponse(
            bool Ok,
            string Status,
            string Error,
            int Region = 0,
            int Zone = 0,
            bool NavmeshAvailable = false,
            bool LineOfSight = false,
            NavigationPoint? SnappedStart = null,
            NavigationPoint? SnappedEnd = null,
            NavigationPoint? Floor = null,
            NavigationPoint[] Points = null)
        {
            public static NavigationResponse Fail(string status, string error, int region = 0, int zone = 0, bool navmeshAvailable = false)
            {
                return new(false, status, error, Region: region, Zone: zone, NavmeshAvailable: navmeshAvailable, Points: Array.Empty<NavigationPoint>());
            }
        }
    }
}
