from shapely.wkt import loads
import s2sphere as s2


class S2Service:
    """
    S2 service for utilizing the S2 functionalities
    """

    @staticmethod
    def wkt_to_cell_ids(field_wkt, resolution_level):
        """
        fetches cell tokens from S2 for the provided wkt field
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
        s2_token_list = []
        for cell_id in cell_ids:
            s2_token_list.append(cell_id.to_token())

        return s2_token_list
