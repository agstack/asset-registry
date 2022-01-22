// The first parameter are the coordinates of the center of the map
// The second parameter is the zoom level
var map = L.map('map').setView([36.7378, -119.7871], 12);

// {s}, {z}, {x} and {y} are placeholders for map tiles
// {x} and {y} are the x/y of where you are on the map
// {z} is the zoom level
// {s} is the subdomain of cartodb
var layer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}.png', {
attribution: 'Rendered by AgStack using open-source ESRI & GeoEye Basemaps'
});

// Now add the layer onto the map
map.addLayer(layer);