"use strict";

// Cent values remain integers through filtering and aggregation; format at display time.
function filterRows(rows, filters) {
  return rows.filter(row => (!filters.year || row.month.slice(0,4) === filters.year)
    && (!filters.segment || row.segment === filters.segment)
    && (!filters.region || row.region === filters.region)
    && (!filters.category || row.category === filters.category));
}
function aggregate(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const name = key ? row[key] : "total";
    if (!groups.has(name)) groups.set(name, {name, revenue_cents:0, gross_profit_cents:0, gross_sales_cents:0, return_credits_cents:0});
    const group = groups.get(name);
    for (const field of ["revenue_cents","gross_profit_cents","gross_sales_cents","return_credits_cents"]) group[field] += Number(row[field] || 0);
  }
  return [...groups.values()];
}
function aging(rows) {
  const buckets = ["Current","1–30 days","31–60 days","61–90 days","90+ days"].map(name=>({name,value:0}));
  for (const row of rows) {
    const d = row.days_overdue;
    const index = d<=0 ? 0 : d<=30 ? 1 : d<=60 ? 2 : d<=90 ? 3 : 4;
    buckets[index].value += row.outstanding_cents;
  }
  return buckets;
}
function percent(n,d) { return d ? `${(n/d*100).toFixed(1)}%` : "—"; }
const money = cents => new Intl.NumberFormat("en-US", {style:"currency",currency:"USD",maximumFractionDigits:0}).format(cents/100);
function compact(cents) {
  const value = cents/100;
  if(Math.abs(value)>=1e6) return `${value<0?"−":""}$${(Math.abs(value)/1e6).toFixed(2)}M`;
  if(Math.abs(value)>=1e3) return `${value<0?"−":""}$${(Math.abs(value)/1e3).toFixed(1)}K`;
  return money(cents);
}
function escaped(value) { return String(value).replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

if (typeof module !== "undefined" && module.exports) module.exports = {filterRows,aggregate,aging,percent};
if (typeof document !== "undefined") {
  let model;
  const byId = id => document.getElementById(id);
  const setText = (id,value)=> { byId(id).textContent=value; };

  function renderTrend(rows, year) {
    let values=aggregate(rows,"month").sort((a,b)=>a.name.localeCompare(b.name));
    // Explicit zero months keep sparse filter selections comparable across time.
    if(year) {
      const existing=new Map(values.map(row=>[row.name,row]));
      values=Array.from({length:12},(_,i)=>{
        const name=`${year}-${String(i+1).padStart(2,"0")}`;
        return existing.get(name) || {name,revenue_cents:0,gross_profit_cents:0};
      });
    }
    if(!rows.length) { byId("trend").innerHTML='<p class="empty">No sales match these filters.</p>'; byId("monthly-table").innerHTML=""; return; }
    const width=1000,height=270,left=63,right=12,top=14,bottom=43;
    const plotW=width-left-right,plotH=height-top-bottom;
    const max=Math.max(1,...values.flatMap(r=>[r.revenue_cents,r.gross_profit_cents]));
    const min=Math.min(0,...values.flatMap(r=>[r.revenue_cents,r.gross_profit_cents]));
    const y=value=>top+(max-value)/(max-min)*plotH;
    let markup=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="trend-title trend-desc"><title id="trend-title">Monthly net revenue and gross profit</title><desc id="trend-desc">${escaped(values.length)} monthly comparisons in US dollars. Exact values are available in the table below.</desc>`;
    for(let tick=0;tick<=4;tick++) {
      const value=min+(max-min)*tick/4, pos=y(value);
      markup+=`<line x1="${left}" y1="${pos}" x2="${width-right}" y2="${pos}" stroke="#e8eeea" stroke-dasharray="3 4"/><text x="${left-12}" y="${pos+4}" text-anchor="end" fill="#8a9a92" font-size="10">${escaped(compact(value))}</text>`;
    }
    const step=plotW/values.length,bw=Math.min(25,step*.28);
    values.forEach((row,index)=>{
      const cx=left+step*(index+.5), baseline=y(0);
      for(const [field,offset,color] of [["revenue_cents",-bw-2,"#257b6b"],["gross_profit_cents",2,"#bdd8b7"]]) {
        const pos=y(row[field]);
        markup+=`<rect x="${cx+offset}" y="${Math.min(pos,baseline)}" width="${bw}" height="${Math.max(.5,Math.abs(baseline-pos))}" rx="2" fill="${color}"><title>${escaped(row.name)} ${field==="revenue_cents"?"net revenue":"gross profit"}: ${escaped(money(row[field]))}</title></rect>`;
      }
      const date=new Date(`${row.name}-01T00:00:00Z`), label=date.toLocaleString("en-US",{month:"short",timeZone:"UTC"});
      if(values.length<=12 || index%2===0) markup+=`<text x="${cx}" y="${height-20}" text-anchor="middle" fill="#8a9a92" font-size="10">${label}${year?"":` ${row.name.slice(2,4)}`}</text>`;
    });
    byId("trend").innerHTML=markup+"</svg>";
    byId("monthly-table").innerHTML=values.map(row=>`<tr><td>${escaped(row.name)}</td><td>${money(row.revenue_cents)}</td><td>${money(row.gross_profit_cents)}</td><td>${percent(row.gross_profit_cents,row.revenue_cents)}</td></tr>`).join("");
  }
  function renderBars(id, rows, key, limit) {
    const groups=aggregate(rows,key).sort((a,b)=>b.revenue_cents-a.revenue_cents).slice(0,limit);
    if(!groups.length){byId(id).innerHTML='<p class="empty">No sales match these filters.</p>';return;}
    const max=Math.max(1,...groups.map(g=>Math.abs(g.revenue_cents)));
    byId(id).innerHTML=groups.map(g=>`<div class="bar-row"><div class="bar-label"><span class="label-text" title="${escaped(g.name)}">${escaped(g.name)}</span><strong>${money(g.revenue_cents)}</strong></div><div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:${Math.abs(g.revenue_cents)/max*100}%"></div></div></div>`).join("");
  }
  function render() {
    const filters=Object.fromEntries(["year","segment","region","category"].map(key=>[key,byId(key).value]));
    const rows=filterRows(model.sales,filters);
    const total=aggregate(rows)[0] || {revenue_cents:0,gross_profit_cents:0,return_credits_cents:0,gross_sales_cents:0};
    setText("revenue",compact(total.revenue_cents));
    setText("profit",compact(total.gross_profit_cents));
    setText("margin",percent(total.gross_profit_cents,total.revenue_cents));
    setText("returns",percent(total.return_credits_cents,total.gross_sales_cents));
    setText("return-detail",`${money(total.return_credits_cents)} in return credits`);
    const priorYear=filters.year ? String(Number(filters.year)-1) : "";
    const prior=aggregate(filterRows(model.sales,{...filters,year:priorYear}))[0];
    const hasPriorYear=filters.year && model.filters.years.includes(priorYear);
    setText("revenue-detail",hasPriorYear && prior?.revenue_cents>0 ? `${((total.revenue_cents/prior.revenue_cents-1)*100).toFixed(1)}% vs ${priorYear} · same filters` : "After return credits · excludes tax");
    renderTrend(rows,filters.year); renderBars("categories",rows,"category",8); renderBars("customers",rows,"customer_name",5);

    const ar=model.receivables.filter(row=>(!filters.segment || row.segment===filters.segment)&&(!filters.region || row.region===filters.region));
    const buckets=aging(ar), max=Math.max(1,...buckets.map(b=>b.value));
    setText("ar-total",compact(ar.reduce((sum,row)=>sum+row.outstanding_cents,0)));
    setText("overdue-total",money(ar.filter(r=>r.days_overdue>0).reduce((sum,row)=>sum+row.outstanding_cents,0)));
    byId("aging").innerHTML=buckets.map(b=>`<div class="aging-row"><span>${escaped(b.name)}</span><div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:${b.value/max*100}%"></div></div><strong>${compact(b.value)}</strong></div>`).join("");
    const stock=model.inventory.filter(row=>!filters.category||row.category===filters.category);
    setText("stock-total",compact(stock.reduce((sum,row)=>sum+row.stock_value_cents,0)));
    setText("low-stock",stock.filter(row=>row.on_hand_units<=row.reorder_point).length);
    setText("product-count",stock.length);
    const overdue=ar.filter(row=>row.days_overdue>0).sort((a,b)=>b.outstanding_cents-a.outstanding_cents);
    byId("watchlist").innerHTML=overdue.slice(0,8).map(row=>`<tr><td>${escaped(row.customer_name)}<span class="secondary">${escaped(row.invoice_id)}</span></td><td>${escaped(row.region)}</td><td>${escaped(row.due_date)}</td><td><span class="days-badge">${row.days_overdue} days</span></td><td>${money(row.outstanding_cents)}</td></tr>`).join("") || '<tr><td colspan="5" class="empty">No overdue invoices for the selected customer filters.</td></tr>';
    setText("watchlist-scope",`${Math.min(8,overdue.length)} of ${overdue.length} overdue invoices. Region and segment filters apply; sales period and product category do not.`);
  }
  async function start() {
    try {
      const response=await fetch("/api/dashboard",{headers:{Accept:"application/json"}});
      if(!response.ok) throw new Error(`Reporting API returned HTTP ${response.status}.`);
      model=await response.json();
      if(!Array.isArray(model.sales)||!Array.isArray(model.receivables)||!Array.isArray(model.inventory)) throw new Error("Reporting API returned an unexpected data structure.");
      for(const key of ["year","segment","region","category"]) {
        const plural={year:"years",segment:"segments",region:"regions",category:"categories"}[key];
        const options=model.filters[plural] || [];
        options.forEach(value=>{const option=document.createElement("option");option.value=value;option.textContent=value;byId(key).append(option);});
        byId(key).addEventListener("change",render);
      }
      byId("year").value=model.filters.years.includes("2025") ? "2025" : "";
      byId("reset").addEventListener("click",()=>{for(const key of ["year","segment","region","category"])byId(key).value=key==="year"&&model.filters.years.includes("2025")?"2025":"";render();});
      const labels={net_revenue:"Net revenue",gross_profit:"Gross profit",gross_margin:"Gross margin",return_credit_rate:"Return credit rate",receivables:"Receivables",overdue:"Overdue balances",inventory:"Inventory value",filter_scope:"Filter scope"};
      byId("definition-list").innerHTML=Object.entries(model.definitions).map(([key,value])=>`<div class="definition"><h3>${escaped(labels[key]||key)}</h3><p>${escaped(value)}</p></div>`).join("");
      render();byId("loading").hidden=true;byId("content").hidden=false;
    } catch(error) {
      byId("loading").hidden=true;byId("error").hidden=false;
      byId("error").textContent=`The dashboard could not load. ${error.message} Start the portfolio server and try again.`;
    }
  }
  start();
}
