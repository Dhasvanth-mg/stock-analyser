"""Market Cap Heatmap — ECharts treemap with aggregated hover."""

import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from utils import inject_css, render_header, page_cfg, render_nav

from data_fetcher import fetch_stock_batch, get_all_symbols

load_dotenv()
page_cfg("Heatmap · NSE")
inject_css()
render_header("🗂️ Market Heatmap", "Hover any tile for aggregated stats · click to zoom")
render_nav("pages/5_Heatmap.py")

# Cap filter
if "cap_filter" not in st.session_state:
    st.session_state["cap_filter"] = "All"

_CAPS  = ["All","Blue Chip","Large Cap","Mid Cap","Small Cap"]
_ICONS = {"All":"🌐","Blue Chip":"🔵","Large Cap":"🟢","Mid Cap":"🟡","Small Cap":"🔴"}
st.markdown('<div class="cap-bar"><span class="cap-label">Cap</span>', unsafe_allow_html=True)
for cap, col in zip(_CAPS, st.columns(len(_CAPS))):
    with col:
        if st.button(f"{_ICONS[cap]} {cap}", use_container_width=True,
                     type="primary" if st.session_state["cap_filter"]==cap else "secondary",
                     key=f"hm_cap_{cap}"):
            st.session_state["cap_filter"] = cap; st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

with st.spinner("Loading stocks…"):
    df = fetch_stock_batch(get_all_symbols(st.session_state["cap_filter"]))

hm = df[df["Price (₹)"] > 0].copy()
if hm.empty:
    st.info("No data."); st.stop()
# Floor so every stock has a visible tile (stocks with missing MC data get minimum)
hm["Mkt Cap (₹Cr)"] = hm["Mkt Cap (₹Cr)"].clip(lower=100)

def _safe(v, fmt="{:.1f}", fb="—"):
    try: return fmt.format(float(v)) if v and float(v)!=0 else fb
    except: return fb

def _node(d, name, level):
    avg_pe  = d["P/E"].replace(0,float("nan")).mean()
    avg_pb  = d["P/B"].replace(0,float("nan")).mean()
    avg_eps = d["EPS"].replace(0,float("nan")).mean()
    avg_bet = d["Beta"].replace(0,float("nan")).mean()
    avg_chg = d["Change %"].mean()
    return {"name":name,"value":[round(d["Mkt Cap (₹Cr)"].sum(),1),round(avg_chg,2)],
            "level":level,
            "totalMcap":f"₹{d['Mkt Cap (₹Cr)'].sum():,.0f} Cr",
            "avgPE":_safe(avg_pe,"{:.1f}"),"avgPB":_safe(avg_pb,"{:.2f}"),
            "avgEPS":"₹"+_safe(avg_eps,"{:.2f}"),
            "totalRev":"—","totalNI":"—",
            "avgDiv":f"{d['Div Yield %'].mean():.2f}%","avgChg":f"{avg_chg:+.2f}%",
            "avgBeta":_safe(avg_bet,"{:.2f}"),"nStocks":str(len(d))}

tree = []
for cap in hm["Cap Category"].unique():
    cap_d = hm[hm["Cap Category"]==cap]
    cn    = _node(cap_d, cap, "cap")
    secs  = []
    for sec in cap_d["Sector"].unique():
        sd  = cap_d[cap_d["Sector"]==sec]
        sn  = _node(sd, sec, "sector")
        stks = []
        for _, s in sd.iterrows():
            stks.append({"name":s["Symbol"],"value":[round(s["Mkt Cap (₹Cr)"],1),round(s["Change %"],2)],
                "level":"stock","fullName":s["Name"],"price":f"₹{s['Price (₹)']:,.2f}",
                "chgRaw":round(s["Change %"],2),"chg":f"{s['Change %']:+.2f}%",
                "mcap":f"₹{s['Mkt Cap (₹Cr)']:,.0f} Cr","pe":_safe(s["P/E"],"{:.1f}"),
                "pb":_safe(s["P/B"],"{:.2f}"),"eps":"₹"+_safe(s["EPS"],"{:.2f}"),
                "rev":"—","ni":"—",
                "div":f"{s['Div Yield %']:.2f}%","beta":_safe(s["Beta"],"{:.2f}"),
                "sector":s["Sector"]})
        sn["children"] = stks; secs.append(sn)
    cn["children"] = secs; tree.append(cn)

tj = json.dumps(tree)

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>body{{margin:0;padding:0;background:#07111d;overflow:hidden}}#c{{width:100%;height:640px}}</style>
</head><body><div id="c"></div><script>
var chart=echarts.init(document.getElementById('c'),'dark',{{renderer:'canvas'}});
var data={tj};
var opt={{backgroundColor:'#07111d',
tooltip:{{trigger:'item',backgroundColor:'#0d1e30',borderColor:'#1e3450',borderWidth:1,padding:12,
  extraCssText:'border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,.6);font-family:monospace',
  formatter:function(p){{var d=p.data;if(!d)return'';
    function row(l,v){{return'<tr><td style="color:#64748b;padding:2px 12px 2px 0">'+l+'</td><td style="color:#e2e8f0;text-align:right">'+v+'</td></tr>';}}
    var h='<div style="min-width:230px"><div style="font-weight:700;font-size:13px;color:#e2e8f0;margin-bottom:6px">'+d.name+'</div>';
    if(d.level==='stock'){{
      h+='<div style="color:#64748b;font-size:11px;margin-bottom:8px">'+(d.fullName||'')+' &bull; '+(d.sector||'')+'</div>';
      var cc=d.chgRaw>=0?'#10b981':'#ef4444';
      h+='<table style="width:100%;border-collapse:collapse;font-size:12px">';
      h+=row('Price',d.price);h+=row('Change','<span style="color:'+cc+';font-weight:600">'+d.chg+'</span>');
      h+=row('Mkt Cap',d.mcap);h+=row('P/E',d.pe);h+=row('P/B',d.pb);h+=row('EPS',d.eps);
      h+=row('Revenue',d.rev);h+=row('Net Inc',d.ni);h+=row('Div Yield',d.div);h+=row('Beta',d.beta);
    }}else{{
      var icon=d.level==='cap'?'🏦':'🏭';
      h+='<div style="color:#64748b;font-size:11px;margin-bottom:8px">'+icon+' '+d.nStocks+' stocks</div>';
      var cc2=(d.avgChg||'').startsWith('+')?'#10b981':'#ef4444';
      h+='<table style="width:100%;border-collapse:collapse;font-size:12px">';
      h+=row('Total Mkt Cap',d.totalMcap);h+=row('Avg P/E',d.avgPE);h+=row('Avg P/B',d.avgPB);
      h+=row('Avg EPS',d.avgEPS);h+=row('Total Revenue',d.totalRev);h+=row('Net Income',d.totalNI);
      h+=row('Avg Div',d.avgDiv);h+=row('Avg Change','<span style="color:'+cc2+';font-weight:600">'+d.avgChg+'</span>');
      h+=row('Avg Beta',d.avgBeta);
    }}
    h+='</table></div>';return h;
  }}}},
visualMap:{{type:'continuous',min:-5,max:5,dimension:1,
  inRange:{{color:['#ef4444','#0d1e30','#10b981']}},show:true,
  orient:'vertical',right:8,top:'center',itemHeight:180,
  text:['+5%','-5%'],textStyle:{{color:'#94a3b8',fontSize:11}},calculable:true}},
series:[{{type:'treemap',data:data,roam:false,nodeClick:'zoomToNode',
  width:'93%',height:'94%',top:'2%',left:'2%',visualDimension:1,
  breadcrumb:{{show:true,bottom:4,height:24,
    itemStyle:{{color:'#0d1e30',textStyle:{{color:'#94a3b8',fontSize:11}}}}}},
  label:{{show:true,formatter:'{{b}}',color:'#e2e8f0',fontSize:11,fontWeight:'bold',overflow:'truncate'}},
  upperLabel:{{show:true,height:26,color:'#e2e8f0',fontSize:12,fontWeight:'bold',
    backgroundColor:'rgba(0,0,0,.35)',padding:[4,8]}},
  itemStyle:{{borderColor:'#07111d',borderWidth:2,gapWidth:2}},
  levels:[
    {{itemStyle:{{borderWidth:0,gapWidth:6}}}},
    {{itemStyle:{{borderWidth:3,borderColor:'#1e3450',gapWidth:4}},upperLabel:{{show:true}}}},
    {{itemStyle:{{borderWidth:2,borderColor:'#0d1e30',gapWidth:2}},upperLabel:{{show:true}}}},
    {{itemStyle:{{borderWidth:1,borderColor:'#07111d',gapWidth:1}}}}
  ]}}]}};
chart.setOption(opt);
window.addEventListener('resize',function(){{chart.resize();}});
</script></body></html>"""

components.html(html, height=660, scrolling=False)

