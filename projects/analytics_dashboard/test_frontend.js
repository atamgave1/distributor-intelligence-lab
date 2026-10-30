"use strict";
const assert=require("node:assert/strict");
const {filterRows,aggregate,aging,percent}=require("./app.js");
const rows=[
 {month:"2024-01",segment:"Retail",region:"East",category:"Tools",revenue_cents:10000,gross_profit_cents:4000,gross_sales_cents:10000,return_credits_cents:0},
 {month:"2025-01",segment:"Retail",region:"East",category:"Tools",revenue_cents:20000,gross_profit_cents:6000,gross_sales_cents:20000,return_credits_cents:0},
 {month:"2025-02",segment:"Retail",region:"East",category:"Tools",revenue_cents:-2000,gross_profit_cents:-800,gross_sales_cents:0,return_credits_cents:2000},
 {month:"2025-01",segment:"Trade",region:"West",category:"Safety",revenue_cents:30000,gross_profit_cents:10000,gross_sales_cents:30000,return_credits_cents:0}
];
const selected=filterRows(rows,{year:"2025",segment:"Retail",region:"East",category:"Tools"});
assert.equal(selected.length,2);
const total=aggregate(selected)[0];
assert.equal(total.revenue_cents,18000);
assert.equal(total.gross_profit_cents,5200);
assert.equal(percent(total.gross_profit_cents,total.revenue_cents),"28.9%");
assert.equal(percent(total.return_credits_cents,total.gross_sales_cents),"10.0%");
assert.equal(filterRows(rows,{region:"Neverland"}).length,0);
assert.equal(percent(0,0),"—");
assert.deepEqual(aging([-1,0,1,30,31,60,61,90,91].map(days_overdue=>({days_overdue,outstanding_cents:100}))).map(b=>b.value),[200,200,200,200,100]);
assert.equal(aggregate(rows,"month").length,3);
console.log("PASS: year/segment/region/category filters; signed returns; weighted margin; return-credit denominator; empty results; all aging boundaries.");
