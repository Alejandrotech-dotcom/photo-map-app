# generate_map_core_China
import os
import exifread
from PIL import Image
from datetime import datetime
from io import BytesIO
import base64
import math

# 仅适用于中国境内坐标
def wgs84_to_gcj02(lat, lon):
    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + \
              0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) +
                20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) +
                40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) +
                320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
        return ret

    def transform_lon(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + \
              0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) +
                20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) +
                40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) +
                300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    def out_of_china(lat, lon):
        return lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271

    a = 6378245.0
    ee = 0.00669342162296594323

    if out_of_china(lat, lon):
        return lat, lon

    d_lat = transform_lat(lon - 105.0, lat - 35.0)
    d_lon = transform_lon(lon - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - ee * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * math.pi)
    d_lon = (d_lon * 180.0) / (a / sqrt_magic * math.cos(rad_lat) * math.pi)
    mg_lat = lat + d_lat
    mg_lon = lon + d_lon
    return mg_lat, mg_lon


def get_exif_data(img_path):
    def _convert_to_degrees(value):
        d = float(value[0].num) / float(value[0].den)
        m = float(value[1].num) / float(value[1].den)
        s = float(value[2].num) / float(value[2].den)
        return d + (m / 60.0) + (s / 3600.0)

    with open(img_path, 'rb') as f:
        tags = exifread.process_file(f)
        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
            lat = _convert_to_degrees(tags['GPS GPSLatitude'].values)
            lon = _convert_to_degrees(tags['GPS GPSLongitude'].values)
            if tags['GPS GPSLatitudeRef'].values != 'N':
                lat = -lat
            if tags['GPS GPSLongitudeRef'].values != 'E':
                lon = -lon

            lat, lon = wgs84_to_gcj02(lat, lon)
        else:
            return None

        date_tag = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
        if date_tag:
            try:
                time = datetime.strptime(str(date_tag), '%Y:%m:%d %H:%M:%S')
            except:
                time = None
        else:
            time = None

        return {
            'path': img_path,
            'lat': lat,
            'lon': lon,
            'time': time
        }

def encode_image_base64(img_path):
    img = Image.open(img_path)
    img.thumbnail((300, 300))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()

def generate_map_china(image_dir):
    files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    points = []

    for f in files:
        path = os.path.join(image_dir, f)
        exif = get_exif_data(path)
        if exif and exif['time']:
            points.append(exif)

    points.sort(key=lambda x: x['time'])
    if not points:
        return None

    amap_key = "af511a0a50058a2e6a69681f64eec795"  # 替换为你自己的高德 Key
    markers_js = ""
    thumbs_html = ""
    path_coords = []

    for i, pt in enumerate(points):
        img_base64 = encode_image_base64(pt['path'])
        popup_html = f"<b>{pt['time']}</b><br><img src='data:image/jpeg;base64,{img_base64}' width='200'>"

        # 129：offset: new AMap.Pixel(10, -30)
        markers_js += f"""
        var marker{i} = new AMap.Marker({{
            position: [{pt['lon']}, {pt['lat']}],
            map: map,
            content: '<div style="color:red; font-size:14px; transform:translate(-50%,-50%)">{i + 1}</div>',
            title: \"{pt['time']}\" 
        }});
        marker{i}.on('click', function() {{
            infoWindow.setContent(`{popup_html}`);
            infoWindow.open(map, marker{i}.getPosition());
        }});
        """

        thumbs_html += f"""
        <div class="thumb-item" onclick="
            map.setCenter(marker{i}.getPosition());
            marker{i}.emit('click', {{target: marker{i}}});
        ">
            <img src="data:image/jpeg;base64,{img_base64}" alt="缩略图"><br>
            {pt['time']}
        </div>
        """

        path_coords.append(f"[{pt['lon']}, {pt['lat']}]")

    polyline_js = f"""
    var polyline = new AMap.Polyline({{
        path: [{','.join(path_coords)}],
        strokeColor: "#3366FF",
        strokeWeight: 1.5
    }});
    polyline.setMap(map);
    """

    center = f"[{points[0]['lon']}, {points[0]['lat']}]"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>轨迹地图</title>
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                height: 100%;
            }}
            #map-container {{
                display: flex;
                height: 100%;
            }}
            #thumbs {{
                width: 200px;
                overflow-y: auto;
                border-right: 1px solid #ccc;
                background: #f8f9fa;
                padding: 6px;
                transition: width 0.3s;
            }}
            #thumbs.collapsed {{
                width: 0;
                padding: 0;
                overflow: hidden;
                border-right: none;
            }}
            .thumb-item {{
                cursor: pointer;
                margin-bottom: 8px;
                text-align: center;
                font-size: 12px;
            }}
            .thumb-item img {{
                width: 100%;
                border-radius: 4px;
                box-shadow: 0 0 3px rgba(0, 0, 0, 0.15);
            }}
            #container {{
                flex-grow: 1;
                transition: margin-left 0.3s;
            }}
            #toggle-btn {{
                position: absolute;
                top: 10px;
                left: 10px;
                z-index: 1000;
                background-color: rgba(255, 255, 255, 0.9);
                border: none;
                padding: 8px 12px;
                border-radius: 4px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                cursor: pointer;
            }}
        </style>
        <script src="https://webapi.amap.com/maps?v=2.0&key={amap_key}"></script>
    </head>
    <body>
        <div id="map-container">
            <div id="thumbs">
                {thumbs_html}
            </div>
            <div id="container"></div>
        </div>
        <button id="toggle-btn">📂 折叠时间轴</button>
        <script>
            var map = new AMap.Map("container", {{
                zoom: 14,
                center: {center}
            }});
            var infoWindow = new AMap.InfoWindow({{offset: new AMap.Pixel(0, -30)}});

            {markers_js}
            {polyline_js}

            // 折叠/展开功能
            const toggleBtn = document.getElementById('toggle-btn');
            const thumbs = document.getElementById('thumbs');
            toggleBtn.addEventListener('click', function() {{
                if (thumbs.classList.contains('collapsed')) {{
                    thumbs.classList.remove('collapsed');
                    toggleBtn.innerText = '📂 折叠时间轴';
                }} else {{
                    thumbs.classList.add('collapsed');
                    toggleBtn.innerText = '📂 展开时间轴';
                }}
            }});
        </script>
    </body>
    </html>
    """

    return html

