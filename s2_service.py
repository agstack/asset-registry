import shapely
from shapely.wkt import loads
import s2sphere as s2
import geopandas as gpd


class S2Service:
    """
    S2 service for utilizing the S2 functionalities
    """

    @staticmethod
    def wkt_to_cell_ids(field_wkt, resolution_level):
        """
        fetches cell ids from S2 for the provided wkt field
        """
        poly = loads(field_wkt)

        longs, lats = poly.exterior.coords.xy
        longs, lats = longs.tolist(), lats.tolist()

        min_level = resolution_level
        max_level = resolution_level
        r = s2.RegionCoverer()
        r.min_level = min_level
        r.max_level = max_level

        lb_lat = min(lats)
        ub_lat = max(lats)
        lb_lon = min(longs)
        ub_lon = max(longs)

        lb = s2.LatLng.from_degrees(lb_lat, lb_lon)
        ub = s2.LatLng.from_degrees(ub_lat, ub_lon)
        cell_ids = r.get_covering(s2.LatLngRect.from_point_pair(lb, ub))

        return cell_ids

    @staticmethod
    def wkt_to_cell_tokens(field_wkt, resolution_level):
        """
        fetches cell tokens from S2 for the provided wkt field
        """
        s2_cell_ids = S2Service.wkt_to_cell_ids(field_wkt, resolution_level)
        s2_token_list = []
        for s2_cell_id in s2_cell_ids:
            s2_token_list.append(s2_cell_id.to_token())

        return s2_token_list

    @staticmethod
    def get_boundary_coverage(s2_cell_ids, polygon, max_resolution_col_name):
        """
        returns lats and longs of the specific s2 cell ids
        """
        s2_index__l19_list = []
        p_gdf = gpd.GeoDataFrame()
        idx = 0
        for s2_cell_id in s2_cell_ids:
            s2_cell = s2.Cell(s2_cell_id)
            vertices = []
            for i in range(0, 4):
                vertex = s2_cell.get_vertex(i)
                latlng = s2.LatLng.from_point(vertex)
                vertices.append((latlng.lng().degrees, latlng.lat().degrees))
            geo = shapely.geometry.Polygon(vertices)
            if polygon.intersects(geo):
                s2_index__l19_list.append(s2_cell_id.to_token())
                p_gdf.loc[idx, max_resolution_col_name] = s2_cell_id.to_token()
                p_gdf.loc[idx, 'geometry'] = geo
            idx += 1

        p_gdf.reset_index(drop=True, inplace=True)
        return p_gdf

    @staticmethod
    def get_cell_token_for_lat_long(lat, long):
        """
        Get the S2 cell tokens for the given lat and long
        Fetching Resolution level 13 and 20 tokens
        :param lat:
        :param long:
        :return:
        """
        s2_cell_token_13 = s2.Cell.from_lat_lng(s2.LatLng.from_degrees(lat, long)).id().parent(13).to_token()
        s2_cell_token_20 = s2.Cell.from_lat_lng(s2.LatLng.from_degrees(lat, long)).id().parent(20).to_token()
        return s2_cell_token_13, s2_cell_token_20
