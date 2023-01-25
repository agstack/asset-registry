import shapely
from shapely.wkt import loads
import s2sphere as s2
import geopandas as gpd


class S2Service:
    """
    S2 service for utilizing the S2 functionalities
    """

    @staticmethod
    def get_bounding_box_cell_ids(latitudes, longitudes, resolution_level):
        min_level = resolution_level
        max_level = resolution_level
        r = s2.RegionCoverer()
        r.min_level = min_level
        r.max_level = max_level

        lb_lat = min(latitudes)
        ub_lat = max(latitudes)
        lb_lon = min(longitudes)
        ub_lon = max(longitudes)

        lb = s2.LatLng.from_degrees(lb_lat, lb_lon)
        ub = s2.LatLng.from_degrees(ub_lat, ub_lon)
        cell_ids = r.get_covering(s2.LatLngRect.from_point_pair(lb, ub))
        return cell_ids

    @staticmethod
    def wkt_to_cell_ids(field_wkt, resolution_level):
        """
        fetches cell ids from S2 for the provided wkt field
        """
        try:
            poly = loads(field_wkt)
            longs, lats = poly.exterior.coords.xy
            longs, lats = longs.tolist(), lats.tolist()
            cell_ids = S2Service.get_bounding_box_cell_ids(lats, longs, resolution_level)
            return cell_ids
        except Exception as e:
            raise Exception(e)


    @staticmethod
    def wkt_to_cell_tokens(field_wkt, resolution_level):
        """
        fetches cell tokens from S2 for the provided wkt field
        """
        try:
            s2_cell_ids = S2Service.wkt_to_cell_ids(field_wkt, resolution_level)
            s2_token_list = []
            for s2_cell_id in s2_cell_ids:
                s2_token_list.append(s2_cell_id.to_token())

            return s2_token_list
        except Exception as e:
            raise Exception(e)

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

    @staticmethod
    def get_cell_tokens_for_bounding_box(latitudes, longitudes, resolution_level=13):
        """
        Fetch the S2 cell tokens for the given Bounding Box
        :param resolution_level:
        :param latitudes:
        :param longitudes:
        :return:
        """
        s2_cell_ids = S2Service.get_bounding_box_cell_ids(latitudes, longitudes, resolution_level)
        s2_token_list = []
        for s2_cell_id in s2_cell_ids:
            s2_token_list.append(s2_cell_id.to_token())
        return s2_token_list
