import React from 'react';
import {DataComponent, ReportSection, RichNarrative, useDataApp} from '../../data-app-public.jsx';
import './report.css';
const number=new Intl.NumberFormat('en-US');
const overview=`## Executive summary

The audited package retains **3,741 complete available drifter trajectories and 39.1M hourly estimates**. Source preservation, field-specific cleaning, target definitions and handover reconciliation have passed their documented checks. These records support starting the 1° short-lag modelling and evaluation programme.

**Predictive accuracy has not been measured.** The primary depth/hardware policy must be decided before modelling the near-15 m scenario. One-year seasonal evidence remains sparse, with some groups and folds impossible to evaluate.`;
const completed=`## 1. Work completed

The data stage now covers acquisition, source-preserving cleaning, origin and target preparation, geometry, observational support and reproducible handover. The architecture audit's additions have been implemented without replacing the research contract.`;
const data=`## 2. Current data overview

The source is the frozen official **NOAA GDP hourly v2.01.1** product. The downloaded trajectories span **6 July 1990 to 31 October 2022 UTC**. Hourly records are processed estimates and overlapping windows, not independent hourly measurements.

There are **463 R-visiting IDs** and **3,278 additional IDs** retained for downstream support. Entire available trajectories are preserved, including positions outside R. The R cohort is a subset of the full cohort; the table's rows must not be added together. Splits are global whole-ID assignments, with the final test kept out of setting selection.`;
const region=`### Release region and transport domain

**R** is the Southern Gulf Stream corridor polygon intersected with 30–35.5°N and 82–73°W. The bounding rectangle alone is not R. Its 1° partition contains approximately **334,502 km² of water**. Whole-R unit mass is allocated by water inside R, including zero weight for 13 boundary-contact-only cells.

**D** is the frozen downstream domain, 81–8°W and 20–55°N. Non-R drifters contribute local downstream evidence. The primary grid is **1°**, anchored at −180° longitude and −90° latitude; aligned 0.5° geometry/support are prepared for later comparison. The finite-domain stopped target remains distinct from unrestricted endpoint occupancy.`;
const quality=`### Quality means preserved values and explicit eligibility

Cleaning keeps original values and separates position, temperature, uncertainty, geometry, timestamp and regime flags. Missing SST does not remove a usable position. Gaps, disappearance and immature follow-up do not become observed physical exits.

The full source-field comparison belongs to the accepted baseline audit. Label semantics additionally have regression and sampled independent evidence; this is not a claim that every semantic predicate on every label was independently recomputed. The later source-position reason correction has no eligibility effect in this snapshot.`;
const supported=`### What research is supported now

The package provides reproducible inputs to **attempt 1° annual and seasonal short-lag transport models**, and to evaluate 7/30-day probability distributions on held-out whole IDs. It also supports separate fixed-undrogued and pooled reference scenarios, first-exit/retention descriptions and whole-R release preparation.

The table reports **eligible hourly-origin labels and distinct IDs**, for actual R origins under the existing fixed-drogued rules. It is observational support, not model accuracy or a universal local sufficiency test. Endpoint labels require the actual matched end location; stopped labels need a complete qualified path only until the horizon or established first exit. These targets must not share a generic valid label.`;
const limits=`### What remains limited

**One year:** the mandatory 365-day analysis stays in scope, but sparse independent support prevents a claim of accurate seasonal one-year forecasting. In train stopped support, 55 of 145 candidate cell–season combinations have zero eligible IDs and 45 have one. A supported combination's median dominant-ID share is 97.73%. Empty validation folds are explicitly not evaluable.

**Depth:** 17 development IDs contribute 41,879 usable drogued D origins from recorded 10 m or missing depth. Another two IDs record depth zero and contribute 3,022 origins. All are retained and separately audited; none of these usable drogued origins lie in R. Drogue attachment does not establish a uniform 15 m operating depth.

The current data do not establish unrestricted one-year domain coverage, accuracy in new regions, or object-specific forecasts for oil, vessels, containers or people.`;
const next=`## 3. Next-stage plan

1. **Architecture decision:** record the primary allowed depth/hardware mixture and sensitivity cohorts. Do not silently delete or relabel non-15 m/unknown equipment.
2. **1° core modelling:** estimate annual and departure-season empirical operators; compare 1/3/5/7-day lags and estimated remainders. Advance the UTC date and operator season at every propagation step. Retain direct anchor references and persistence/destination-climatology baselines.
3. **7/30-day development validation:** compare the same targets and cases using log loss, Brier score and calibration, preserving outside and unresolved-support mass. Select lag, pooling and regularization from development evidence; use whole-ID uncertainty and lock settings before final test.
4. **365-day assessment:** attempt annual and seasonally pooled/shrunk predictions; publish sparse and non-evaluable groups. Do not use long-lived survivors as the entire short-lag cohort or rebalance IDs to fill seasons.
5. **Refinement after evidence:** consider 0.5° and broader regional transfer only when the core runs and development results justify them. Optional challengers remain subsequent experiments, not immediate dependencies.

The next completed milestone is a reproducible core-model evaluation package. Improving prediction accuracy is the objective; its success must be demonstrated by held-out probability scores and calibration.`;
export function ReportContent(){
 const {snapshot,visible,canEdit,mode,appTitle,setAppTitle}=useDataApp();
 const rows=id=>snapshot.queries[id].rows;
 const prose=(id,queryId,title,value)=>visible(id)&&<ReportSection id={id} title={title} queryId={queryId} sourceRows={rows(queryId)} showHeading={false} className='report-section'><RichNarrative id={`${id}:text`} value={value} label={`Edit ${title}`}/></ReportSection>;
 const table=(id,qid,title,columns)=>visible(id)&&<DataComponent id={id} queryId={qid} kind='table' title={title} sourceRows={rows(qid)} displayRows={rows(qid)}>
  <div className='stage-table-scroll'><table className='stage-table' aria-label={title} data-reviewed-rows><thead><tr>{columns.map(c=><th key={c.key} className={c.numeric?'numeric':''}>{c.label}</th>)}</tr></thead><tbody>{rows(qid).map((row,i)=><tr key={i}>{columns.map(c=><td key={c.key} className={c.numeric?'numeric':''}>{typeof row[c.key]==='number'?number.format(row[c.key]):row[c.key]}</td>)}</tr>)}</tbody></table></div>
 </DataComponent>;
 return <article className='report-content stage-report' aria-label='DATA3001 data preparation stage report'>
  <header className='report-hero'><h1 data-data-app-title contentEditable={canEdit&&mode==='edit'} suppressContentEditableWarning
   onBlur={canEdit&&mode==='edit'?e=>setAppTitle(e.currentTarget.textContent.trim()||appTitle):undefined}>{appTitle}</h1>
   <RichNarrative id='stage-report:subtitle' value='UNSW DATA3001 · Where Things End Up · Stage report · 13 October 2026' className='report-deck'/></header>
  <ReportSection id='stage-summary' title='Executive summary' queryId='cohort' queryIds={['cohort','limits','quality']} sourceRowsByQuery={{cohort:rows('cohort'),limits:rows('limits'),quality:rows('quality')}} showHeading={false}><RichNarrative id='stage-summary:text' value={overview}/></ReportSection>
  {prose('completed-work','completed_tasks','Work completed',completed)}
  {table('completed-table','completed_tasks','Completed preparation deliverables',[{key:'task',label:'Task'},{key:'details',label:'Result'}])}
  {prose('data-overview','cohort','Data overview',data)}
  {table('cohort-table','cohort','Downloaded trajectory cohorts',[{key:'cohort',label:'Cohort'},{key:'IDs',label:'IDs',numeric:true},{key:'sourceHourlyRecords',label:'Source hourly records',numeric:true},{key:'trainIDs',label:'Train IDs',numeric:true},{key:'validationIDs',label:'Validation IDs',numeric:true},{key:'lockedTestIDs',label:'Locked test IDs',numeric:true}])}
  {prose('region-overview','regions','Regions and grid',region)}
  {prose('quality-overview','quality','Quality and status',quality)}
  {table('quality-table','quality','Quality and evidence status',[{key:'item',label:'Aspect'},{key:'result',label:'Evidence'},{key:'status',label:'Status'}])}
  {prose('supported-research','R_anchor_support','Supported research',supported)}
  {table('anchor-table','R_anchor_support','R fixed-drogued label support',[{key:'horizonDays',label:'Days',numeric:true},{key:'target',label:'Target'},{key:'trainPairs',label:'Train labels',numeric:true},{key:'trainIDs',label:'Train IDs',numeric:true},{key:'validationPairs',label:'Validation labels',numeric:true},{key:'validationIDs',label:'Validation IDs',numeric:true}])}
  {prose('limitations','limits','Support limitations',limits)}
  {prose('next-plan','next_steps','Next-stage plan',next)}
  <RichNarrative id='stage-report:scope' value='Evidence is from the audited local preparation package and its 13 October 2026 handover additions. The underlying hourly source ends in 2022. Data Contract v1.0 remains the research authority. This report summarizes status; it creates no new eligibility policy or model result.' className='stage-scope'/>
 </article>;
}
