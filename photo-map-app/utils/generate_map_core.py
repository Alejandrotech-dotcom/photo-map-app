# generate_map_core
import os
import exifread
from PIL import Image
from datetime import datetime
from io import BytesIO
import base64
import math

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
        else:
            return None

        date_tag = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
        time = datetime.strptime(str(date_tag), '%Y:%m:%d %H:%M:%S') if date_tag else None

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

def generate_map(image_dir):
    files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    points = [get_exif_data(os.path.join(image_dir, f)) for f in files]
    points = [p for p in points if p and p['time']]
    points.sort(key=lambda x: x['time'])
    if not points:
        return None

    markers_js = ""
    thumbs_html = ""
    path_coords = []

    for i, pt in enumerate(points):
        img_base64 = encode_image_base64(pt['path'])
        popup_html = f"<b>{pt['time']}</b><br><img src='data:image/jpeg;base64,{img_base64}' width='200'>"

        markers_js += f"""
        var marker{i} = L.marker([{pt['lat']}, {pt['lon']}], {{
            title: "{pt['time']}",
            icon: L.divIcon({{
                html: '<div style="color:red; font-size:14px; transform:translate(-50%,-50%)">{i + 1}</div>',
                className: 'number-icon'
            }})
        }}).addTo(map);
        marker{i}.bindPopup(`{popup_html}`);
        """

        thumbs_html += f"""
        <div class="thumb-item" onclick="
            map.setView([{pt['lat']}, {pt['lon']}], map.getZoom());
            marker{i}.openPopup();
        ">
            <img src="data:image/jpeg;base64,{img_base64}" alt="缩略图"><br>
            {pt['time']}
        </div>
        """

        path_coords.append(f"[{pt['lat']}, {pt['lon']}]")

    polyline_js = f"""
    L.polyline([{','.join(path_coords)}], {{
        color: '#3388ff',
        weight: 1.5
    }}).addTo(map);
    """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>OSM轨迹地图</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <style>
            html, body {{
                margin: 0;
                height: 100%;
                overflow: hidden;
            }}
            #map-container {{
                display: flex;
                height: 100vh;
                transition: all 0.3s;
            }}
            #thumbs {{
                width: 220px;
                overflow-y: auto;
                background: #f8f9fa;
                padding: 6px;
                transition: all 0.3s ease;
            }}
            #thumbs.collapsed {{
                width: 0;
                padding: 0;
                overflow: hidden;
            }}
            .thumb-item {{
                cursor: pointer;
                margin-bottom: 8px;
                padding: 4px;
            }}
            .leaflet-popup-content img {{
                max-width: 200px !important;
            }}
            #map {{
                flex: 1;
                transition: all 0.3s ease;
            }}
            #toggle-btn {{
                position: absolute;
                top: 10px;
                left: 10px;
                z-index: 1000;
                background: #007bff;
                color: white;
                border: none;
                padding: 6px 10px;
                cursor: pointer;
                border-radius: 4px;
            }}
        </style>
    </head>
    <body>
        <button id="toggle-btn">≡</button>
        <div id="map-container">
            <div id="thumbs">{thumbs_html}</div>
            <div id="map"></div>
        </div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var map = L.map('map',{{zoomControl: false}}).setView([{points[0]['lat']}, {points[0]['lon']}], 14);
            L.control.zoom({{ position: 'topright' }}).addTo(map);
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            }}).addTo(map);
    
            {markers_js}
            {polyline_js}
    
            // 折叠逻辑 + 自动地图重绘
            document.getElementById("toggle-btn").addEventListener("click", function() {{
                const thumbs = document.getElementById("thumbs");
                thumbs.classList.toggle("collapsed");
    
                // 等 CSS 动画完成后刷新地图尺寸
                setTimeout(() => {{
                    map.invalidateSize();
                }}, 310);  // 310ms > 0.3s transition
            }});
        </script>
    </body>
    </html>
    """
    return html