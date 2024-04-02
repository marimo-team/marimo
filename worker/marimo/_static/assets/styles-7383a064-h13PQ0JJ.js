import{G as V}from"./graph-2XWsaN9T.js";import{b0 as D,b1 as M,b2 as R,u as F,N as C,A as _}from"./index-R2Y2oCNK.js";import{J as U,n as N,l as y,o as j,c as $,i as G,p as E,v as H,q as J,K}from"./mermaid-4SjVPaEp.js";import{r as W}from"./index-8fae9850-qAA5bNRM.js";import{c as X}from"./channel-xC5HTf2u.js";function Q(e){return typeof e=="string"?new D([document.querySelectorAll(e)],[document.documentElement]):new D([R(e)],M)}function pe(e,l){return!!e.children(l).length}function be(e){return L(e.v)+":"+L(e.w)+":"+L(e.name)}var Y=/:/g;function L(e){return e?String(e).replace(Y,"\\:"):""}function Z(e,l){l&&e.attr("style",l)}function fe(e,l,c){l&&e.attr("class",l).attr("class",c+" "+e.attr("class"))}function ue(e,l){var c=l.graph();if(U(c)){var a=c.transition;if(F(a))return a(e)}return e}function O(e,l){var c=e.append("foreignObject").attr("width","100000"),a=c.append("xhtml:div");a.attr("xmlns","http://www.w3.org/1999/xhtml");var i=l.label;switch(typeof i){case"function":a.insert(i);break;case"object":a.insert(function(){return i});break;default:a.html(i)}Z(a,l.labelStyle),a.style("display","inline-block"),a.style("white-space","nowrap");var d=a.node().getBoundingClientRect();return c.attr("width",d.width).attr("height",d.height),c}const z={},ee=function(e){const l=Object.keys(e);for(const c of l)z[c]=e[c]},q=function(e,l,c,a,i,d){const u=a.select(`[id="${c}"]`);Object.keys(e).forEach(function(p){const r=e[p];let g="default";r.classes.length>0&&(g=r.classes.join(" ")),g=g+" flowchart-label";const w=N(r.styles);let t=r.text!==void 0?r.text:r.id,s;if(y.info("vertex",r,r.labelType),r.labelType==="markdown")y.info("vertex",r,r.labelType);else if(j($().flowchart.htmlLabels)){const m={label:t.replace(/fa[blrs]?:fa-[\w-]+/g,k=>`<i class='${k.replace(":"," ")}'></i>`)};s=O(u,m).node(),s.parentNode.removeChild(s)}else{const m=i.createElementNS("http://www.w3.org/2000/svg","text");m.setAttribute("style",w.labelStyle.replace("color:","fill:"));const k=t.split(G.lineBreakRegex);for(const T of k){const v=i.createElementNS("http://www.w3.org/2000/svg","tspan");v.setAttributeNS("http://www.w3.org/XML/1998/namespace","xml:space","preserve"),v.setAttribute("dy","1em"),v.setAttribute("x","1"),v.textContent=T,m.appendChild(v)}s=m}let b=0,o="";switch(r.type){case"round":b=5,o="rect";break;case"square":o="rect";break;case"diamond":o="question";break;case"hexagon":o="hexagon";break;case"odd":o="rect_left_inv_arrow";break;case"lean_right":o="lean_right";break;case"lean_left":o="lean_left";break;case"trapezoid":o="trapezoid";break;case"inv_trapezoid":o="inv_trapezoid";break;case"odd_right":o="rect_left_inv_arrow";break;case"circle":o="circle";break;case"ellipse":o="ellipse";break;case"stadium":o="stadium";break;case"subroutine":o="subroutine";break;case"cylinder":o="cylinder";break;case"group":o="rect";break;case"doublecircle":o="doublecircle";break;default:o="rect"}l.setNode(r.id,{labelStyle:w.labelStyle,shape:o,labelText:t,labelType:r.labelType,rx:b,ry:b,class:g,style:w.style,id:r.id,link:r.link,linkTarget:r.linkTarget,tooltip:d.db.getTooltip(r.id)||"",domId:d.db.lookUpDomId(r.id),haveCallback:r.haveCallback,width:r.type==="group"?500:void 0,dir:r.dir,type:r.type,props:r.props,padding:$().flowchart.padding}),y.info("setNode",{labelStyle:w.labelStyle,labelType:r.labelType,shape:o,labelText:t,rx:b,ry:b,class:g,style:w.style,id:r.id,domId:d.db.lookUpDomId(r.id),width:r.type==="group"?500:void 0,type:r.type,dir:r.dir,props:r.props,padding:$().flowchart.padding})})},P=function(e,l,c){y.info("abc78 edges = ",e);let a=0,i={},d,u;if(e.defaultStyle!==void 0){const n=N(e.defaultStyle);d=n.style,u=n.labelStyle}e.forEach(function(n){a++;const p="L-"+n.start+"-"+n.end;i[p]===void 0?(i[p]=0,y.info("abc78 new entry",p,i[p])):(i[p]++,y.info("abc78 new entry",p,i[p]));let r=p+"-"+i[p];y.info("abc78 new link id to be used is",p,r,i[p]);const g="LS-"+n.start,w="LE-"+n.end,t={style:"",labelStyle:""};switch(t.minlen=n.length||1,n.type==="arrow_open"?t.arrowhead="none":t.arrowhead="normal",t.arrowTypeStart="arrow_open",t.arrowTypeEnd="arrow_open",n.type){case"double_arrow_cross":t.arrowTypeStart="arrow_cross";case"arrow_cross":t.arrowTypeEnd="arrow_cross";break;case"double_arrow_point":t.arrowTypeStart="arrow_point";case"arrow_point":t.arrowTypeEnd="arrow_point";break;case"double_arrow_circle":t.arrowTypeStart="arrow_circle";case"arrow_circle":t.arrowTypeEnd="arrow_circle";break}let s="",b="";switch(n.stroke){case"normal":s="fill:none;",d!==void 0&&(s=d),u!==void 0&&(b=u),t.thickness="normal",t.pattern="solid";break;case"dotted":t.thickness="normal",t.pattern="dotted",t.style="fill:none;stroke-width:2px;stroke-dasharray:3;";break;case"thick":t.thickness="thick",t.pattern="solid",t.style="stroke-width: 3.5px;fill:none;";break;case"invisible":t.thickness="invisible",t.pattern="solid",t.style="stroke-width: 0;fill:none;";break}if(n.style!==void 0){const o=N(n.style);s=o.style,b=o.labelStyle}t.style=t.style+=s,t.labelStyle=t.labelStyle+=b,n.interpolate!==void 0?t.curve=E(n.interpolate,C):e.defaultInterpolate!==void 0?t.curve=E(e.defaultInterpolate,C):t.curve=E(z.curve,C),n.text===void 0?n.style!==void 0&&(t.arrowheadStyle="fill: #333"):(t.arrowheadStyle="fill: #333",t.labelpos="c"),t.labelType=n.labelType,t.label=n.text.replace(G.lineBreakRegex,`
`),n.style===void 0&&(t.style=t.style||"stroke: #333; stroke-width: 1.5px;fill:none;"),t.labelStyle=t.labelStyle.replace("color:","fill:"),t.id=r,t.classes="flowchart-link "+g+" "+w,l.setEdge(n.start,n.end,t,a)})},te=function(e,l){return l.db.getClasses()},re=async function(e,l,c,a){y.info("Drawing flowchart");let i=a.db.getDirection();i===void 0&&(i="TD");const{securityLevel:d,flowchart:u}=$(),n=u.nodeSpacing||50,p=u.rankSpacing||50;let r;d==="sandbox"&&(r=_("#i"+l));const g=d==="sandbox"?_(r.nodes()[0].contentDocument.body):_("body"),w=d==="sandbox"?r.nodes()[0].contentDocument:document,t=new V({multigraph:!0,compound:!0}).setGraph({rankdir:i,nodesep:n,ranksep:p,marginx:0,marginy:0}).setDefaultEdgeLabel(function(){return{}});let s;const b=a.db.getSubGraphs();y.info("Subgraphs - ",b);for(let f=b.length-1;f>=0;f--)s=b[f],y.info("Subgraph - ",s),a.db.addVertex(s.id,{text:s.title,type:s.labelType},"group",void 0,s.classes,s.dir);const o=a.db.getVertices(),m=a.db.getEdges();y.info("Edges",m);let k=0;for(k=b.length-1;k>=0;k--){s=b[k],Q("cluster").append("text");for(let f=0;f<s.nodes.length;f++)y.info("Setting up subgraphs",s.nodes[f],s.id),t.setParent(s.nodes[f],s.id)}q(o,t,l,g,w,a),P(m,t);const T=g.select(`[id="${l}"]`),v=g.select("#"+l+" g");if(await W(v,t,["point","circle","cross"],"flowchart",l),H.insertTitle(T,"flowchartTitleText",u.titleTopMargin,a.db.getDiagramTitle()),J(t,T,u.diagramPadding,u.useMaxWidth),a.db.indexNodes("subGraph"+k),!u.htmlLabels){const f=w.querySelectorAll('[id="'+l+'"] .edgeLabel .label');for(const x of f){const S=x.getBBox(),h=w.createElementNS("http://www.w3.org/2000/svg","rect");h.setAttribute("rx",0),h.setAttribute("ry",0),h.setAttribute("width",S.width),h.setAttribute("height",S.height),x.insertBefore(h,x.firstChild)}}Object.keys(o).forEach(function(f){const x=o[f];if(x.link){const S=_("#"+l+' [id="'+f+'"]');if(S){const h=w.createElementNS("http://www.w3.org/2000/svg","a");h.setAttributeNS("http://www.w3.org/2000/svg","class",x.classes.join(" ")),h.setAttributeNS("http://www.w3.org/2000/svg","href",x.link),h.setAttributeNS("http://www.w3.org/2000/svg","rel","noopener"),d==="sandbox"?h.setAttributeNS("http://www.w3.org/2000/svg","target","_top"):x.linkTarget&&h.setAttributeNS("http://www.w3.org/2000/svg","target",x.linkTarget);const A=S.insert(function(){return h},":first-child"),B=S.select(".label-container");B&&A.append(function(){return B.node()});const I=S.select(".label");I&&A.append(function(){return I.node()})}}})},we={setConf:ee,addVertices:q,addEdges:P,getClasses:te,draw:re},le=(e,l)=>{const c=X,a=c(e,"r"),i=c(e,"g"),d=c(e,"b");return K(a,i,d,l)},ae=e=>`.label {
    font-family: ${e.fontFamily};
    color: ${e.nodeTextColor||e.textColor};
  }
  .cluster-label text {
    fill: ${e.titleColor};
  }
  .cluster-label span,p {
    color: ${e.titleColor};
  }

  .label text,span,p {
    fill: ${e.nodeTextColor||e.textColor};
    color: ${e.nodeTextColor||e.textColor};
  }

  .node rect,
  .node circle,
  .node ellipse,
  .node polygon,
  .node path {
    fill: ${e.mainBkg};
    stroke: ${e.nodeBorder};
    stroke-width: 1px;
  }
  .flowchart-label text {
    text-anchor: middle;
  }
  // .flowchart-label .text-outer-tspan {
  //   text-anchor: middle;
  // }
  // .flowchart-label .text-inner-tspan {
  //   text-anchor: start;
  // }

  .node .label {
    text-align: center;
  }
  .node.clickable {
    cursor: pointer;
  }

  .arrowheadPath {
    fill: ${e.arrowheadColor};
  }

  .edgePath .path {
    stroke: ${e.lineColor};
    stroke-width: 2.0px;
  }

  .flowchart-link {
    stroke: ${e.lineColor};
    fill: none;
  }

  .edgeLabel {
    background-color: ${e.edgeLabelBackground};
    rect {
      opacity: 0.5;
      background-color: ${e.edgeLabelBackground};
      fill: ${e.edgeLabelBackground};
    }
    text-align: center;
  }

  /* For html labels only */
  .labelBkg {
    background-color: ${le(e.edgeLabelBackground,.5)};
    // background-color: 
  }

  .cluster rect {
    fill: ${e.clusterBkg};
    stroke: ${e.clusterBorder};
    stroke-width: 1px;
  }

  .cluster text {
    fill: ${e.titleColor};
  }

  .cluster span,p {
    color: ${e.titleColor};
  }
  /* .cluster div {
    color: ${e.titleColor};
  } */

  div.mermaidTooltip {
    position: absolute;
    text-align: center;
    max-width: 200px;
    padding: 2px;
    font-family: ${e.fontFamily};
    font-size: 12px;
    background: ${e.tertiaryColor};
    border: 1px solid ${e.border2};
    border-radius: 2px;
    pointer-events: none;
    z-index: 100;
  }

  .flowchartTitleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${e.textColor};
  }
`,he=ae;export{Z as a,O as b,ue as c,fe as d,be as e,we as f,he as g,pe as i,Q as s};
