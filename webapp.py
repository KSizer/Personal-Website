from flask import Flask, render_template, Markup
import json
import logging

import pandas as pd
import geopandas as gpd

from bokeh.models import GeoJSONDataSource, ColorBar, EqHistColorMapper, ColumnDataSource, Range1d, RadioButtonGroup
from bokeh.plotting import figure
from bokeh.tile_providers import CARTODBPOSITRON_RETINA, get_provider
from bokeh.palettes import brewer
from bokeh.models.tickers import BinnedTicker
from bokeh.models.formatters import NumeralTickFormatter
from bokeh.models.tools import WheelZoomTool
from bokeh.models.callbacks import CustomJS
from bokeh.embed import components
from bokeh.resources import CDN

import folium



app = Flask(__name__)

@app.route('/plot/')
def plot():


    gdf = gpd.read_file(open("merge__uk_regions__uk_covid_d.geojson"))
    tile_provider = get_provider(CARTODBPOSITRON_RETINA)
    gdf[['cases','deaths','firstVacc','secondVacc','thirdVacc','population']] = gdf[['cases','deaths','firstVacc','secondVacc','thirdVacc','population']].apply(pd.to_numeric)
    gdf['cases_per_cap'] = gdf['cases']/gdf['population']*100000
    gdf['perc_first_vacc'] = gdf['firstVacc']/gdf['population']
    gdf['perc_second_vacc'] = gdf['secondVacc']/gdf['population']
    gdf['perc_third_vacc'] = gdf['thirdVacc']/gdf['population']

    geo_source = GeoJSONDataSource(geojson=json.dumps(json.loads(gdf.to_json())))

    palette = brewer['YlOrRd'][8]
    palette = palette[::-1]
    vals = gdf['cases_per_cap']
    #Instantiate LinearColorMapper that linearly maps numbers in a range, into a sequence of colors.
    color_mapper = EqHistColorMapper(palette = palette, low = vals.min(), high = vals.max(), bins = 8)
    color_bar = ColorBar(color_mapper=color_mapper, label_standoff=8,
                    location=(0,0), orientation='horizontal', title = "Cases per 100k",
                    ticker = BinnedTicker(mapper = color_mapper), formatter = NumeralTickFormatter(format = '0a'))

    TOOLTIPS = [
        ('Region Name:', '@rgn19nm'),
        ('Cases per 100k:', '@cases_per_cap{0.0a}')
    ]

    p = figure(plot_width=800, plot_height=800,
           x_range=(-1008000, 255000), y_range=(6400000, 8240000),
           x_axis_type="mercator", y_axis_type="mercator",tooltips = TOOLTIPS
           ,tools = "pan,wheel_zoom,box_zoom,reset,tap")

    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_color = None

    p.xaxis.major_tick_line_color = None
    p.xaxis.minor_tick_line_color = None

    p.yaxis.major_tick_line_color = None
    p.yaxis.minor_tick_line_color = None

    p.xaxis.major_label_text_font_size = '0pt'
    p.yaxis.major_label_text_font_size = '0pt'


    p.toolbar.active_scroll = p.select_one(WheelZoomTool)

    p.patches('xs','ys', source=geo_source, fill_alpha=0.6, line_width=0.5, line_color='black', fill_color={'field' :"cases_per_cap" , 'transform': color_mapper}, nonselection_alpha=0.6)
    p.add_tile(tile_provider)
    p.add_layout(color_bar, 'below')

    line_data = pd.read_csv('uk_covid_data_timeseries.csv', keep_default_na=False)

    line_data['date'] = pd.to_datetime(line_data['date'],format="%d/%m/%Y")

    line_data = line_data.sort_values(by=['date'])

    line_source = ColumnDataSource(data = dict(date=[],cases=[]))

    l = figure(plot_width = 750, plot_height = 200, x_axis_type="datetime", sizing_mode = 'stretch_both')

    l.y_range = Range1d(0, 40000)

    l.line('date','cases',source = line_source)


    LABELS = ["Scale y-axis", "Don't scale y-axis"]

    radio_button_group = RadioButtonGroup(labels=LABELS, active=0)
    radio_button_group.js_on_click(CustomJS(args = dict(line_graph = l),code="""
                                    console.log('radio_button_group: active=' + this.active, this.toString())
                                    line_graph.y_range.end = 40000
                                    """))


    modal_update_text = CustomJS(args=dict(geo_source = geo_source, line_source = line_source, pd_data = line_data.to_dict(orient='records'), line_graph = l, rbg = radio_button_group),code = """
                        const inds = cb_obj.indices;
                        const geo_data = geo_source.data;
                        var line_data = line_source.data;
                        const selection = rbg.active;
                        if(Object.keys(inds).length === 0){
                            console.log("unselect")
                        }
                        else{
                            let nf = new Intl.NumberFormat('en-UK')

                            document.getElementById('modal-title').innerHTML = geo_data['rgn19nm'][inds[0]]
                            document.getElementById('region-info-cases').innerHTML = nf.format(geo_data['cases'][inds[0]])
                            document.getElementById('region-info-deaths').innerHTML = nf.format(geo_data['deaths'][inds[0]])
                            document.getElementById('region-info-pop').innerHTML = nf.format(geo_data['population'][inds[0]])
                            document.getElementById('region-info-vacc1').innerHTML = parseFloat(geo_data['perc_first_vacc'][inds[0]]*100).toFixed(2) + '%'
                            document.getElementById('region-info-vacc2').innerHTML = parseFloat(geo_data['perc_second_vacc'][inds[0]]*100).toFixed(2) + '%'
                            document.getElementById('region-info-vacc3').innerHTML = parseFloat(geo_data['perc_third_vacc'][inds[0]]*100).toFixed(2) + '%'

                            var filtered_pd_data = pd_data.filter(x=>x.areaName === geo_data['rgn19nm'][inds[0]]);

                            line_data['date'] = []
                            line_data['cases'] = []

                            for (let i = 0; i < filtered_pd_data.length; i++) {
                                line_data['date'].push(filtered_pd_data[i]['date'])
                                line_data['cases'].push(filtered_pd_data[i]['cases'])
                            }

                            line_source.change.emit();

                            //if you want auto y axis scaling, uncomment the lines below

                            console.log(selection)

                            if(selection === 0){
                                const num_cases = line_data['cases'].map(str => {return Number(str);})

                                line_graph.y_range.end = Math.max.apply(Math, num_cases)*1.1
                            }



                            cb_obj.indices = []

                            var region_modal = new bootstrap.Modal(document.getElementById('region-info-modal'))
                            region_modal.toggle()


                        }

                    """)

    geo_source.selected.js_on_change('indices', modal_update_text)

    script, div = components((p,l,radio_button_group))

    div1 = div[0]
    div2 = div[1]
    div3 = div[2]

    cdn_js = CDN.js_files[0]
    cdn_widgets = CDN.js_files[2]

    return render_template('covid_map.html', script=script, div1=div1, div2=div2, div3=div3, cdn_js=cdn_js, cdn_widgets=cdn_widgets)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about/')
def about():
    return render_template('about.html')

@app.route('/route_finder/')
def route_finder():

    def update_map(route):

        folium.PolyLine(
            route['route'],
            weight=8,
            color='blue',
            opacity=0.6
        ).add_to(m)

        folium.Marker(
            location=route['start_point'],
            icon=folium.Icon(icon='play', color='green'),
        ).add_to(m)

        folium.Marker(
            location=route['end_point'],
            icon=folium.Icon(icon='cutlery', color='red'),
            popup="Drivetime: " +  str(round(route['duration']/60,2)) +' min\nWebsite: <a href=' + str(route['website']) + '>Link</a>' + '\nDrivethrough: ' + str(route['drive_through'])
        ).add_to(m)

        m.fit_bounds(m.get_bounds())


        return m

    filtered_route_df = pd.read_pickle('filtered_route_df.pkl')

    m = folium.Map(zoom_start=5)

    for i in range(0,len(filtered_route_df)):
        update_map(filtered_route_df.loc[i,:])

    route_map = m._repr_html_()

    m2 = folium.Map()
    point_list = pd.read_pickle("point_list.pkl")

    folium.Polygon(
        locations = point_list,
        fill = True,
        fillColor = 'red'
    ).add_to(m2)

    folium.Marker(
        location=[53.3585523, -2.865193],
        icon=folium.Icon(icon='cutlery', color='green', prefix='fa')
    ).add_to(m2)

    m2.fit_bounds(m2.get_bounds())

    catch_map = m2._repr_html_()

    return render_template('route_finder.html',route_map = route_map,catch_map=catch_map)

@app.route('/network_graphing/')
def network_graphing():

    similarity_table = pd.read_csv("twitch_similarity_data.csv").to_html(index=False, classes="table table-bordered table-striped table-sm").replace("<thead>", "<thead class='table-dark'>").replace("<th>", "<th class='text-center'>")
    twitch_channels_table = pd.read_csv("twitch_channel_list.csv").to_html(index=False, classes="table table-bordered table-striped table-sm").replace("<thead>", "<thead class='table-dark'>").replace("<th>", "<th class='text-center'>")
    youtube_channels_table = pd.read_csv("youtube_channel_list.csv").to_html(index=False, classes="table table-bordered table-striped table-sm").replace("<thead>", "<thead class='table-dark'>").replace("<th>", "<th class='text-center'>")
    return render_template('network_graphing.html', similarity_table=similarity_table, twitch_channels_table=twitch_channels_table, youtube_channels_table=youtube_channels_table)

if __name__ == "__main__":
    app.run(debug=True)




