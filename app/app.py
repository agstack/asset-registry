import geojson
import json
import shapely.wkt
import pandas as pd
from flask import Flask, render_template, jsonify, request, url_for
import hashlib
import h3
import plotly
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import urllib
import urllib.request
import urllib.parse as urlparse
from urllib.parse import urlencode
from flask import make_response
import folium
import geojson
import s2sphere as s2
import s2cell
import uuid
import geopandas as gpd





################  FUNCTIONS
def isValidPolygon(poly_wkt):

	return True

def isValidMethod(hashMethodStr):

	return True

def isValidLoc(lat,lon):

	return True


def checkIfGeoIdExists(GeoId, table):

	cmdStr = 'postgresql+psycopg2://'+username+':'+passwd+'@'+hostname+':'+port+'/'+database
	engine = create_engine(cmdStr)
	conn = engine.raw_connection()
	conn.autocommit = True
	cursor = conn.cursor()
	sql = 'select \"s2_fieldGeoId\" from '+table
	cursor.execute(sql)
	res = cursor.fetchall()
	resultList = [x[0] for x in res]
	
	conn.commit()
	conn.close()
	
	if GeoId in resultList:
		return True
	else:
		return False

def putPolyInDB(asset_df, tableName):
	
	#To put the data for the asset
	cmdStr = 'postgresql+psycopg2://'+username+':'+passwd+'@'+hostname+':'+port+'/'+database
	#print(cmdStr)
	engine = create_engine(cmdStr)
	conn = engine.raw_connection()
	cur = conn.cursor()

	if not checkIfGeoIdExists(GeoId, tableName):
		asset_df.to_sql(tableName, engine, if_exists='append', index=False, 
						dtype={'s2_normalizedFieldWKT': Geometry('POLYGON', srid= 4326)})

	conn.close()
	return

def getPolyForGeoId(GeoId):
	tableName = 'asset_registry'
	resp = ''
	cmdStr = 'postgresql+psycopg2://'+username+':'+passwd+'@'+hostname+':'+port+'/'+database
	engine = create_engine(cmdStr)
	conn = engine.raw_connection()
	conn.autocommit = True
	cursor = conn.cursor()
	#sql = 'select * from '+tableName
	
	sqlStr = """SELECT * FROM asset_registry WHERE \"s2_fieldGeoId\" = '"""+str(GeoId)+"""';"""
	cursor.execute(sqlStr)
	results = cursor.fetchall()
	conn.close()

	if len(results)>0:
		#print(results)
		responseDict = {}
		for res in results:
			s2_GeoId = res[2]
			if s2_GeoId == GeoId:
				responseDict['uuid']=res[0]
				#responseDict['s2_cellid']=res[1]
				responseDict['geoid']=res[2]
				responseDict['wkt']=res[3]
		return json.loads(json.dumps(responseDict))
	else:
		return

def fixZinPolygon(poly):
	coordsList = [[poly.exterior.xy[0][x],poly.exterior.xy[1][x]] for x in range(0,len(poly.exterior.xy[0]))]
	new_poly = shapely.geometry.Polygon(coordsList)
	return new_poly

def getPolyForLatLon(lat,lon):
	
	pt = shapely.geometry.Point(float(lon), float(lat))
	
	s2_cell = s2.Cell.from_lat_lng(s2.LatLng.from_degrees(float(lat), float(lon)))
	s2_cid = s2_cell.id().parent(6)
	s2_cellid_token = s2_cid.to_token()
	
	#print(s2_cellid_token)
	
	cmdStr = 'postgresql+psycopg2://'+username+':'+passwd+'@'+hostname+':'+port+'/'+database
	engine = create_engine(cmdStr)
	#sql = """SELECT * FROM asset_registry;"""
	#Select the rows that are in the 100 sq km grid and search
	sqlStr = """SELECT * FROM asset_registry WHERE \"s2_cellid\" = '"""+str(s2_cellid_token)+"""';"""
	a_df = pd.read_sql(sqlStr, engine)
	for i,row in a_df.iterrows():
		a_df.loc[i,'geom'] = wkb.loads(row.GEOM_WKT, hex=True)
	a_gdf = gpd.GeoDataFrame(a_df, geometry=a_df.geom)
	a_gdf = a_gdf.drop(columns=['geom'], axis=1)
	
	ret_gdf = a_gdf[a_gdf['geometry'].intersects(pt)]
	ret_gdf.reset_index(drop=True, inplace=True)
	#Make json from the first row
	responseDict = {}
	responseDict['uuid']=ret_gdf['uuid'].iloc[0]
	#responseDict['s2_cellid']=ret_gdf['s2_cellid'].iloc[0]
	responseDict['geoid']=ret_gdf['s2_fieldGeoId'].iloc[0]
	responseDict['wkt']=ret_gdf['s2_normalizedFieldWKT'].iloc[0]
	
	return json.loads(json.dumps(responseDict))


def getGeoJsonForPolyWKTs(user_fieldWKT, s2_fieldWKT):
	
	user_poly = shapely.wkt.loads(user_fieldWKT)
	user_polyDict = shapely.geometry.mapping(user_poly)
	user_fieldDict = {}
	user_fieldDict['type']='Feature'
	user_fieldDict['properties']={'userType': 'user'}
	user_fieldDict['geometry']=user_polyDict
	
	s2_poly = shapely.wkt.loads(s2_fieldWKT)
	s2_polyDict = shapely.geometry.mapping(s2_poly)
	s2_fieldDict = {}
	s2_fieldDict['type']='Feature'
	s2_fieldDict['properties']={'userType': 's2'}
	s2_fieldDict['geometry']=s2_polyDict
	
	return [user_fieldDict, s2_fieldDict]

def getGeoJsonFCForPolyWKTs(user_fieldWKT, s2_fieldWKT):
	user_poly = shapely.wkt.loads(user_fieldWKT)
	s2_poly = shapely.wkt.loads(s2_fieldWKT)
	polygon_list = [user_poly, s2_poly]

	field_list = []
	idx=0
	for p in polygon_list:
		field = json.loads(gpd.GeoSeries([p]).to_json())
		if idx==0:
			field['features'][0]['properties'] = {'userType': 'user'}
		elif idx==1:
			field['features'][0]['properties'] = {'userType': 's2'}
		field = json.dumps(field)
		field_list.append(field)
		idx=idx+1


	return field_list

def getLatLonList(user_fieldWKT, s2_fieldWKT):
	user_poly = shapely.wkt.loads(user_fieldWKT)
	user_poly_coords = [[user_poly.exterior.xy[1][x],user_poly.exterior.xy[0][x]] for x in range(0,len(user_poly.exterior.xy[0]))]
	s2_poly = shapely.wkt.loads(s2_fieldWKT)
	s2_poly_coords = [[s2_poly.exterior.xy[1][x],s2_poly.exterior.xy[0][x]] for x in range(0,len(s2_poly.exterior.xy[0]))]

	polygon_list = [user_poly, s2_poly]

	LatLonList = [user_poly_coords,s2_poly_coords]

	return LatLonList

###########################

#create the app
app = Flask(__name__)
app.config['JSON_SORT_KEYS']=False

error_res = {}



################  ROUTES
@app.route('/')
@app.route('/index')
@app.route('/home')
def index():
	return render_template('index.html')


@app.route('/registerField')
def registerField():

	fields = []
	returnType = 'json' #default

	poly_wkt = request.args.get('wkt')

	formatType = request.args.get('format')
	#This is the H3 resolution level 
	if formatType is None:
		formatType = 'json'
	else:
		formatType = formatType
	if not ((formatType=='json') | (formatType=='html')):
		formatType='html'


	h3_resolution_level = request.args.get('h3_resolution_level')
	#This is the H3 resolution level 
	if h3_resolution_level is None:
		h3_resolution_level = 13
	else:
		h3_resolution_level = int(h3_resolution_level)

	s2_resolution_level = request.args.get('s2_resolution_level')
	#This is the H3 resolution level 
	if s2_resolution_level is None:
		s2_resolution_level = 20
	else:
		s2_resolution_level = int(s2_resolution_level)

	s2_search_level = request.args.get('s2_search_level')
	#This is the H3 resolution level 
	if s2_search_level is None:
		s2_search_level = 6
	else:
		s2_search_level = int(s2_search_level)

	#Not going to get this from the user
	h3_hash_method = 'H3 API + sha-256'
	s2_hash_method = 'S2 API + sha-256'

	if not isValidPolygon(poly_wkt):
		return 'Invalid Polygon'
	else:

		poly = shapely.wkt.loads(poly_wkt)
		latlon = [poly.centroid.xy[1][0], poly.centroid.xy[0][0]]
		#print(latlon)

		lons = poly.exterior.xy[0]
		lats = poly.exterior.xy[1]

		#get the search index s2_seach (level-6 S2 -- approx 100 sq km)
		[lon_centroid, lat_centroid] = [poly.centroid.x, poly.centroid.y]
		s2_cell = s2.Cell.from_lat_lng(s2.LatLng.from_degrees(lat_centroid, lon_centroid))
		s2_cid = s2_cell.id().parent(s2_search_level)
		s2_cellid_token = s2_cid.to_token()

		#for every lat-lon pair, create an H3_13 index and make a tuple of these 
		h3_source = 'https://h3geo.org/'
		s2_source = 'https://s2geometry.io/; https://pypi.org/project/s2cell/'

		H3fieldBoundaryList = []
		S2fieldBoundaryList = []
		for i, lat in enumerate(lats):
			lon=lons[i]
			h3_ind = h3.geo_to_h3(lat, lon, h3_resolution_level)

			#S2 implementation
			cell = s2.Cell.from_lat_lng(s2.LatLng.from_degrees(lat, lon))
			#convert to a cellid of level=s2_level_default
			cid = cell.id().parent(s2_resolution_level)
			s2_ind = cid.to_token()

			#make a list of these
			S2fieldBoundaryList.append(s2_ind)
			H3fieldBoundaryList.append(h3_ind) 

		H3fieldBoundaryTuple = tuple(H3fieldBoundaryList)
		S2fieldBoundaryTuple = tuple(S2fieldBoundaryList)

		#get the "normalized field" for H3
		geojonList = h3.h3_set_to_multi_polygon(H3fieldBoundaryTuple, geo_json=True)
		H3fieldBoundaryCentroids = [[shapely.geometry.Polygon(x[0]).centroid.xy[0][0],shapely.geometry.Polygon(x[0]).centroid.xy[1][0]] for x in geojonList if len(x[0])>2]
		#Put the last oint the same as the first to complete a Polygon
		H3fieldBoundaryCentroids.insert(len(H3fieldBoundaryCentroids),H3fieldBoundaryCentroids[0])
		H3new_poly = shapely.geometry.Polygon(H3fieldBoundaryCentroids)
		H3new_poly_wkt = H3new_poly.wkt

		#get the "normalized field" for S2
		S2fieldBoundaryCentroids = [[s2cell.token_to_lat_lon(x)[1], s2cell.token_to_lat_lon(x)[0]] for x in S2fieldBoundaryList]
		#Put the last oint the same as the first to complete a Polygon
		S2fieldBoundaryCentroids.insert(len(S2fieldBoundaryCentroids),S2fieldBoundaryCentroids[0])
		S2new_poly = shapely.geometry.Polygon(S2fieldBoundaryCentroids)
		S2new_poly_wkt = S2new_poly.wkt

		#find the intersection area as a percentage of area of the original Polygon
		#Find intersection area
		h3_intersection = poly.intersection(H3new_poly)
		h3_percent_area = round((h3_intersection.area / poly.area * 100),2)

		#find the intersection area as a percentage of area of the original Polygon
		#Find intersection area
		s2_intersection = poly.intersection(S2new_poly)
		s2_percent_area = round((s2_intersection.area / poly.area * 100),2)


		m = hashlib.sha256() #invoking the encrption function sha256 (better than md5)
		
		for s in H3fieldBoundaryTuple:
			m.update(s.encode())
		H3fieldBoundaryHash = m.hexdigest() # --> 'fd9332bfd562a03ca94987c828068d828b24ad711b908aadbe5039632ebd39d5'


		for s in S2fieldBoundaryTuple:
			m.update(s.encode())
		S2fieldBoundaryHash = m.hexdigest()


		#mAKE THE HASHING METHOD
		H3hashMethodDict = {}
		H3hashMethodDict['h3_method']=h3_hash_method
		H3hashMethodDict['h3_resolution']=h3_resolution_level
		H3hashMethodDict['h3_reference']=h3_source

		S2hashMethodDict = {}
		S2hashMethodDict['s2_method']=s2_hash_method
		S2hashMethodDict['s2_resolution']=s2_resolution_level
		S2hashMethodDict['s2_reference']=s2_source


		#mAKE THE RETURN json
		#Masking out the h3 returned values

		fieldRegistryDict = {}
		uid = str(uuid.uuid4())
		fieldRegistryDict['uuid']=uid
		#fieldRegistryDict['h3_fieldGeoId']=H3fieldBoundaryHash
		#fieldRegistryDict['h3_method']=H3hashMethodDict
		fieldRegistryDict['s2_fieldGeoId']=S2fieldBoundaryHash
		fieldRegistryDict['s2_cellid']=s2_cellid_token
		fieldRegistryDict['s2_method']=S2hashMethodDict
		#fieldRegistryDict['h3_percentageOverlap']=h3_percent_area
		fieldRegistryDict['s2_percentageOverlap']=s2_percent_area
		fieldRegistryDict['originalFieldWKT']=poly_wkt
		#fieldRegistryDict['h3_normalizedFieldWKT']=H3new_poly_wkt
		fieldRegistryDict['s2_normalizedFieldWKT']=S2new_poly_wkt


		#create a json for the registration
		fieldRegistryJSON = json.dumps(fieldRegistryDict, indent=4)

		#field_list = getGeoJsonFCForPolyWKTs(poly_wkt, S2new_poly_wkt)
		LatLonCoordsList = getLatLonList(poly_wkt, S2new_poly_wkt)

		if formatType=='json':
			return jsonify(json.loads(fieldRegistryJSON))

		elif formatType=='html':
			return render_template('map.html', fields=LatLonCoordsList, centeroid=latlon)


#main to run the app
if __name__ == '__main__':
	#extra_files = [updated_data_available_file,]
	extra_files = []
	app.run(host='0.0.0.0' , port=5000, debug=True, extra_files=extra_files)
