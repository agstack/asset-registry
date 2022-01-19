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

################  useful data transformations and dictionaries
property_dict = {
	'bdod': 'Bulk density of the fine earth fraction',
	'cec': 'Cation Exchange Capacity of the soil',
	'cfvo': 'Volumetric fraction of coarse fragments (> 2 mm)',
	'clay': 'Proportion of clay particles (< 0.002 mm) in the fine earth fraction',
	'sand': 'Proportion of sand particles (> 0.05 mm) in the fine earth fraction',
	'silt': 'Proportion of silt particles (>= 0.002 mm and <= 0.05 mm) in the fine earth fraction',
	'nitrogen': 'Total nitrogen (N)', 
	'ocd': 'Organic carbon density',
	'ocs': 'Organic carbon stocks',
	'phh2o': 'Soil pH',
	'soc': 'Soil organic carbon content in the fine earth fraction'
}
soilsList = [
'Acrisols',
'Alisols',
'Andosols',
'Anthrosols',
'Arenosols',
'Calcisols',
'Cambisols',
'Chernozem',
'Cryosols',
'Durisols',
'Ferralsols',
'Fluvisols',
'Gleysols',
'Gypsisols',
'Histosol',
'Kastanozems',
'Leptosols',
'Lixisols',
'Luvisols',
'Nitisols',
'Phaeozems',
'Planosols',
'Plinthosols',
'Podzols',
'Regosols',
'Retisols',
'Solonchaks',
'Solonetz',
'Stagnosols',
'Technosols',
'Umbrisols',
'Vertisols',
]
soils_dict = dict()
""" remove the link
for s in soilsList:
	if s[-1]=='s':
		url = 'https://en.wikipedia.org/wiki/' + s[0:-1]
	else:
		url = 'https://en.wikipedia.org/wiki/' + s
	soils_dict.update({s: url})
"""

def getSoilPropertiesDF(propertyCodeStr, data):
	
	allDepth_df = pd.DataFrame()

	#first get the subset by name
	for i in range(len(data['properties']['layers'])):
		propName = data['properties']['layers'][i]['name']
		if (propName==propertyCodeStr):
			
			#get the unit measure
			um = data['properties']['layers'][i]['unit_measure']
			fac = um['d_factor']
			unitStr_target = um['target_units']
			unitStr_mapped = um['mapped_units']
			
			
			data_code = data['properties']['layers'][i]
			num_depths = len(data_code['depths'])
			for d in range(num_depths):
				data_at_depth = data_code['depths'][d]
				row_label = data_at_depth['label']
				vals = data_at_depth['values']
				rng = data_at_depth['range']
				
				top_depth = rng['top_depth']
				bottom_depth = rng['bottom_depth']
				unit_depth = rng['unit_depth']
				
				df = pd.DataFrame(list(vals.values())).T
				df = df / fac
				
				df.columns = list(vals.keys())
				cols = ['Depth'] + ['Top_Depth', 'Botton_Depth', 'Units_Depth'] + df.columns.tolist()
				
				df['Depth'] = row_label
				df['Top_Depth'] = top_depth
				df['Botton_Depth'] = bottom_depth
				df['Units_Depth'] = unit_depth
				
				df = df[cols]
				allDepth_df = allDepth_df.append(df, ignore_index=True)
		else:
			continue
	
	return [unitStr_mapped, fac, unitStr_target, propertyCodeStr, property_dict[propertyCodeStr]], allDepth_df

def getSoilPropertiesDF2(propertyCodeStr, data):
	
	allDepth_df = pd.DataFrame()

	#first get the subset by name
	for i in range(len(data['properties']['layers'])):
		propName = data['properties']['layers'][i]['name']
		if (propName==propertyCodeStr):
			
			#get the unit measure
			um = data['properties']['layers'][i]['unit_measure']
			fac = um['d_factor']
			unitStr_target = um['target_units']
			unitStr_mapped = um['mapped_units']
			
			
			data_code = data['properties']['layers'][i]
			num_depths = len(data_code['depths'])
			for d in range(num_depths):
				data_at_depth = data_code['depths'][d]
				row_label = data_at_depth['label']
				vals = data_at_depth['values']
				rng = data_at_depth['range']
				
				top_depth = rng['top_depth']
				bottom_depth = rng['bottom_depth']
				unit_depth = rng['unit_depth']
				
				df = pd.DataFrame(list(vals.values())).T
				df = df / fac
				
				df.columns = list(vals.keys())
				cols = ['Depth'] + ['Top_Depth', 'Botton_Depth', 'Units_Depth'] + df.columns.tolist()
				
				df['Depth'] = row_label
				df['Top_Depth'] = top_depth
				df['Botton_Depth'] = bottom_depth
				df['Units_Depth'] = unit_depth
				
				df = df[cols]
				allDepth_df = allDepth_df.append(df, ignore_index=True)
		else:
			continue
	
	#fix the allDepth_df
	df = allDepth_df[['Depth','mean']]
	df = df.rename(columns={'mean':propertyCodeStr})
	df = df.drop(columns=['Depth'], axis=1)
	
	return [unitStr_mapped, fac, unitStr_target, propertyCodeStr, property_dict[propertyCodeStr]], df



def getAWCMean(silt, clay, BD):
	#https://journals.lww.com/soilsci/Abstract/1985/07000/Estimating_Available_Water_Holding_Capacity_of.7.aspx#:~:text=Available%20water%2Dstorage%20capacity%20(AWSC,(r2%20%3D%200.92)%3A%20AWSCcore%20%3D
	if not silt.index.name=='Depth':
		silt.set_index('Depth', drop=True, inplace=True)
	silt = silt[['mean']]
	silt = silt.astype('float')
	
	if not clay.index.name=='Depth':
		clay.set_index('Depth', drop=True, inplace=True)
	clay = clay[['mean']]
	clay = clay.astype('float')
	
	if not BD.index.name=='Depth':
		BD.set_index('Depth', drop=True, inplace=True)
	BD = BD[['mean']]
	BD = BD.astype('float')
	
	AWSC = 14.01 + 0.03*(silt * clay) - 8.78*BD
	AWSC.rename(columns={'mean':'AWSC'}, inplace=True)
	AWSC = AWSC.round(2)
	#units are %Volume
	unitsStr = '%vol [volume-fraction]'
	
	return unitsStr, AWSC, 'Available water holding capacity'


def getKsatMean(silt, sand, clay, BD):

	if not silt.index.name=='Depth':
		silt.set_index('Depth', drop=True, inplace=True)
	silt = silt[['mean']]
	silt = silt.astype('float')

	if not clay.index.name=='Depth':
		clay.set_index('Depth', drop=True, inplace=True)
	clay = clay[['mean']]
	clay = clay.astype('float')

	if not sand.index.name=='Depth':
		sand.set_index('Depth', drop=True, inplace=True)
	sand = sand[['mean']]
	sand = sand.astype('float')

	if not BD.index.name=='Depth':
		BD.set_index('Depth', drop=True, inplace=True)
	BD = BD[['mean']]
	BD = BD.astype('float')

	b0=2.17
	b1=0.9387
	b2=-0.8026
	b3=0.0037
	b4=-0.017
	b5=0
	b6=0.0025
	b7=0
	b8=0
	b9=0
	#Ksat is in cm/day, clay (CL) and sand (SA) are expressed in % and bulk density (BD) is in g/cm3 or kg/dm3
	log_Ksat = b0 + b1*BD + b2*BD.pow(2) + b3*clay + b4*BD*clay + b5*clay.pow(2) + b6*sand + b7*BD*sand + b8*clay*sand + b9*sand.pow(2)
	log_Ksat = log_Ksat[['mean']]
	Ksat = log_Ksat.apply(lambda x: np.exp(x))
	Ksat.rename(columns = {'mean':'Ksat'}, inplace=True)
	units = 'cm/day'
	
	#Convert to inches / hr
	Ksat_inchesPerHr = Ksat * 0.0164042
	units_inchesPerHr = 'in/hr'

	return units_inchesPerHr, Ksat_inchesPerHr, 'Saturated hydraulic conductivity'



def getSoils(lat,lon):
	number_classes=10
	#url_loc = 'https://rest.soilgrids.org/soilgrids/v2.0/classification/query?'+'lon='+str(lon)+'&lat='+str(lat)+'&number_classes='+str(number_classes)
	url_loc = 'https://rest.isric.org/soilgrids/v2.0/classification/query?'+'lon='+str(lon)+'&lat='+str(lat)+'&number_classes='+str(number_classes)
	with urllib.request.urlopen(url_loc) as response:
		loc_data = json.load(response)
	
	soilsList = loc_data['wrb_class_probability']
	colsList=['SOIL','PROB','INFO_URL']
	colsList=['SOIL','PROB']
	soils_df = pd.DataFrame()
	i=0
	for s in soilsList:
		soilName = s[0]
		prob = s[1]
		
		try:
			urlStr = soils_dict[soilName]
			#soilLink = '<a href='+urlStr+'>'+sn+'</a>' 
			soilLink = urlStr 
			#print(soilLink)
		except:
			#didn't find the link
			if soilName[-1]=='s':
				sn = soilName[0:-1]
			else:
				sn = soilName
			urlStr = 'https://en.wikipedia.org/wiki/'+sn
			#soilLink = '<a href='+urlStr+'>'+sn+'</a>' 
			soilLink = urlStr 
			#print(soilLink)
		
		soils_df.loc[i,'SOIL']=soilName
		soils_df.loc[i,'PROB']=prob
		#soils_df.loc[i,'INFO_URL']=soilLink
		i=i+1
	
	
	soils_df = soils_df[colsList]
	
	#newCols = ['Soil Type', 'Percentage', 'More Information']
	newCols = ['Soil Type', 'Percentage']
	soils_df.columns = newCols
	
	return soils_df


def getPropertiesDF(lat,lon):
	#API call for the details about a point
	"""
	Query a single pixel point on the soilgrids stack, returning a GeoJSON
	layer: soilgrids layer name to be queried
	depth: specific depth to be queried
	values: statistical values Optional[List] = LayerQuery
	"""

	#API #2 is meta data
	url_layers = 'https://rest.isric.org/soilgrids/v2.0/properties/layers'
	with urllib.request.urlopen(url_layers) as response:
		layer_data = json.load(response)
	#get the list of properties
	propertiesList = []
	length = len(layer_data['layers'])
	for idx in range(length):
		p = layer_data['layers'][idx]['property']
		propertiesList.append(p)

	#to get the meta data for any property
	depths=[]
	values = []
	#modify the property list
	propertiesList = ['bdod',
	 'cec',
	 'cfvo',
	 'soc',
	 'nitrogen',
	 'ocd',
	 'phh2o',
	 'clay',
	 'sand',
	 'silt']
	
	prop_to_find = 'nitrogen'
	for idx in range(length):
		p = layer_data['layers'][idx]['property']
		if (p==prop_to_find):
			info = layer_data['layers'][idx]['layer_structure']
			for i in range(len(info)):
				depths.append(info[i]['range'])
				values.append(info[i]['values'])
	valuesList = values[1]
	prop_url = ''
	for p in propertiesList:
		prop_url = prop_url + '&property='+str(p)

	value_url = ''
	valuesList=['mean']
	for v in valuesList:
		value_url = value_url + '&value='+str(v)

	depth_url = ''
	depths=['0-5cm']
	for d in depths:
		depth_url = depth_url + '&depth='+str(d)

	main_url = 'https://rest.isric.org/soilgrids/v2.0/properties/query?' + 'lon='+str(lon)+'&lat='+str(lat)
	url_details = main_url + prop_url + depth_url + value_url
	with urllib.request.urlopen(url_details) as response:
		data = json.load(response) 

	propertyResult = pd.DataFrame()
	i=0
	for p in propertiesList:
		prop_mean_value = getSoilPropertiesDF2(p, data)[1].iloc[0][0]
		prop_units = getSoilPropertiesDF2(p, data)[0][2]
		prop_desc = getSoilPropertiesDF2(p, data)[0][4]
		propertyResult.loc[i,'Name']=p
		propertyResult.loc[i,'Mean Value in Top-Soil']=prop_mean_value
		propertyResult.loc[i,'Units']=prop_units
		propertyResult.loc[i,'Description']=prop_desc
		i=i+1

	#Lets; do KSat
	ksat_tuple = getKsatMean(getSoilPropertiesDF('silt', data)[1], getSoilPropertiesDF('sand', data)[1], getSoilPropertiesDF('clay', data)[1], getSoilPropertiesDF('bdod', data)[1])
	nameStr = ksat_tuple[1].columns.tolist()[0]
	valStr = ksat_tuple[1].iloc[0][0]
	unitsStr = ksat_tuple[0]
	descStr = ksat_tuple[2]
	propertyResult.loc[len(propertyResult.index)] = [nameStr, valStr, unitsStr, descStr]

	#Now let's do AWC
	awc_tuple = getAWCMean(getSoilPropertiesDF('silt', data)[1], getSoilPropertiesDF('clay', data)[1], getSoilPropertiesDF('bdod', data)[1])
	nameStr = awc_tuple[1].columns.tolist()[0]
	valStr = awc_tuple[1].iloc[0][0]
	unitsStr = awc_tuple[0]
	descStr = awc_tuple[2]
	propertyResult.loc[len(propertyResult.index)] = [nameStr, valStr, unitsStr, descStr]
	
	renamedCols = ['Acronym', 'Mean Value in Top-Soil', 'Units', 'Property']
	propertyResult.columns=renamedCols
	subsetCols = ['Property', 'Mean Value in Top-Soil', 'Units']
	propertyResult = propertyResult[subsetCols]
	
	#round to 2 decimal places for Mean Value
	propertyResult['Mean Value in Top-Soil'] = propertyResult['Mean Value in Top-Soil'].round(2)
	
	return propertyResult



################  FUNCTIONS
def isValidPolygon(poly_wkt):

	return True

def isValidMethod(hashMethodStr):

	return True

def isValidLoc(lat,lon):

	return True

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


@app.route('/soilInfo')
def soilInfo():

	returnType = 'json' #default

	formatType = request.args.get('format')
	if formatType is None:
		formatType = 'html'
	

	lat = float(request.args.get('lat'))
	lon = float(request.args.get('lon'))

	#print(lat, lon)
	# return null if the point isn't inside the US
	if not isValidLoc(lat,lon):
		return 'Not Valid US Land Location'
	else:
		soils_df = getSoils(lat,lon)
		soils_json = soils_df.to_json(orient='records')

		prop_df = getPropertiesDF(lat,lon)
		prop_json = prop_df.to_json(orient='records')

		if formatType=='html':
			#Create the soil properties json
			#################################

			#figSoilBarChart = px.bar(soils_df, y='Soil Type', x='Percentage', text='More Information', orientation='h')
			figSoilBarChart = px.bar(soils_df, y='Soil Type', x='Percentage', orientation='h')

			figSoilBarChartJSON = json.dumps(figSoilBarChart, cls=plotly.utils.PlotlyJSONEncoder)


			figPropertiesTable = go.Figure(data=[go.Table(
				header=dict(values=list(prop_df.columns),
							line_color='white',
							font_color='white',
							font_size=18,
							fill_color='royalblue',
							align='center'),
				cells=dict(values=[prop_df['Property'], prop_df['Mean Value in Top-Soil'], prop_df['Units']],
						   fill_color='white',
						   font_size=16,
						   line_color='lightslategray',
						   align='center'))
			])
			figPropertiesTableJSON = json.dumps(figPropertiesTable, cls=plotly.utils.PlotlyJSONEncoder)

			return render_template('soil_dashboard.html', soilBarChart=figSoilBarChartJSON, soilPropTable=figPropertiesTableJSON)
		else: #return json
			soilInfo = {}
			soilInfo['soilComposition']=json.loads(soils_json)
			soilInfo['soilAttributes']=json.loads(prop_json)
			soilInfoJSON = jsonify(soilInfo)

			return soilInfoJSON


@app.route('/registerField')
def registerField():

	returnType = 'json' #default

	poly_wkt = request.args.get('wkt')


	soilsBool = request.args.get('soilinfo')
	if soilsBool is None:
		soilsBool = False
	else:
		soilsBool=True

	h3_resolution_level = request.args.get('h3_resolution_level')
	#This is the H3 resolution level 
	if h3_resolution_level is None:
		h3_resolution_level = 14
	else:
		h3_resolution_level = int(h3_resolution_level)

	s2_resolution_level = request.args.get('s2_resolution_level')
	#This is the H3 resolution level 
	if s2_resolution_level is None:
		s2_resolution_level = 21
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
		fieldRegistryDict = {}
		uid = str(uuid.uuid4())
		fieldRegistryDict['uuid']=uid
		fieldRegistryDict['h3_fieldGeoId']=H3fieldBoundaryHash
		fieldRegistryDict['h3_method']=H3hashMethodDict
		fieldRegistryDict['s2_fieldGeoId']=S2fieldBoundaryHash
		fieldRegistryDict['s2_cellid']=s2_cellid_token
		fieldRegistryDict['s2_method']=S2hashMethodDict
		fieldRegistryDict['h3_percentageOverlap']=h3_percent_area
		fieldRegistryDict['s2_percentageOverlap']=s2_percent_area
		fieldRegistryDict['originalFieldWKT']=poly_wkt
		fieldRegistryDict['h3_normalizedFieldWKT']=H3new_poly_wkt
		fieldRegistryDict['s2_normalizedFieldWKT']=S2new_poly_wkt

		
		if soilsBool:
			#Create the soil properties json
			#################################
			#First get a representative point in the Polygon
			lon=poly.representative_point().xy[0][0]
			lat=poly.representative_point().xy[1][0]

			soils_df = getSoils(lat,lon)
			soils_json = soils_df.to_json(orient='records')
			figSoilBarChart = px.bar(soils_df, y='Soil Type', x='Percentage', text='More Information', orientation='h')

			prop_df = getPropertiesDF(lat,lon)
			prop_json = prop_df.to_json(orient='records')

			figPropertiesTable = go.Figure(data=[go.Table(
				header=dict(values=list(prop_df.columns),
							line_color='white',
							font_color='white',
							font_size=18,
							fill_color='royalblue',
							align='center'),
				cells=dict(values=[prop_df['Property'], prop_df['Mean Value in Top-Soil'], prop_df['Units']],
						   fill_color='white',
						   font_size=16,
						   line_color='lightslategray',
						   align='center'))
			])
			#################################
			fieldRegistryDict['soilComposition']=json.loads(soils_json)
			fieldRegistryDict['soilAttributes']=json.loads(prop_json)


		#create a json for the registration
		fieldRegistryJSON = json.dumps(fieldRegistryDict, indent=2)

		return fieldRegistryJSON


#main to run the app
if __name__ == '__main__':
	#extra_files = [updated_data_available_file,]
	extra_files = []
	app.run(host='0.0.0.0' , port=5000, debug=True, extra_files=extra_files)
