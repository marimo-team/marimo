import{U as j,c as nt,s as ce,g as le,t as ue,u as de,b as fe,a as he,x as me,k as ke,l as pt,h as ye,i as ge,v as pe}from"./mermaid-4SjVPaEp.js";import{y as St,g as Et,A as ht,bj as be,bk as xe,bl as ve,bm as Te,bn as we,bo as Pt,bp as Nt,bq as Bt,br as Rt,bs as Ht,bt as Gt,bu as Xt,bv as _e,bw as De,bx as Ce,by as Se,bz as Ee,bA as Ae,bB as Me}from"./index-R2Y2oCNK.js";function Le(t){return t}var kt=1,vt=2,Tt=3,mt=4,jt=1e-6;function Ie(t){return"translate("+t+",0)"}function Ye(t){return"translate(0,"+t+")"}function Fe(t){return e=>+t(e)}function We(t,e){return e=Math.max(0,t.bandwidth()-e*2)/2,t.round()&&(e=Math.round(e)),s=>+t(s)+e}function Ve(){return!this.__axis}function Zt(t,e){var s=[],a=null,r=null,h=6,f=6,x=3,C=typeof window<"u"&&window.devicePixelRatio>1?0:.5,v=t===kt||t===mt?-1:1,F=t===mt||t===vt?"x":"y",E=t===kt||t===Tt?Ie:Ye;function _(w){var H=a??(e.ticks?e.ticks.apply(e,s):e.domain()),m=r??(e.tickFormat?e.tickFormat.apply(e,s):Le),D=Math.max(h,0)+x,L=e.range(),M=+L[0]+C,O=+L[L.length-1]+C,P=(e.bandwidth?We:Fe)(e.copy(),C),G=w.selection?w.selection():w,N=G.selectAll(".domain").data([null]),z=G.selectAll(".tick").data(H,e).order(),k=z.exit(),T=z.enter().append("g").attr("class","tick"),g=z.select("line"),y=z.select("text");N=N.merge(N.enter().insert("path",".tick").attr("class","domain").attr("stroke","currentColor")),z=z.merge(T),g=g.merge(T.append("line").attr("stroke","currentColor").attr(F+"2",v*h)),y=y.merge(T.append("text").attr("fill","currentColor").attr(F,v*D).attr("dy",t===kt?"0em":t===Tt?"0.71em":"0.32em")),w!==G&&(N=N.transition(w),z=z.transition(w),g=g.transition(w),y=y.transition(w),k=k.transition(w).attr("opacity",jt).attr("transform",function(n){return isFinite(n=P(n))?E(n+C):this.getAttribute("transform")}),T.attr("opacity",jt).attr("transform",function(n){var u=this.parentNode.__axis;return E((u&&isFinite(u=u(n))?u:P(n))+C)})),k.remove(),N.attr("d",t===mt||t===vt?f?"M"+v*f+","+M+"H"+C+"V"+O+"H"+v*f:"M"+C+","+M+"V"+O:f?"M"+M+","+v*f+"V"+C+"H"+O+"V"+v*f:"M"+M+","+C+"H"+O),z.attr("opacity",1).attr("transform",function(n){return E(P(n)+C)}),g.attr(F+"2",v*h),y.attr(F,v*D).text(m),G.filter(Ve).attr("fill","none").attr("font-size",10).attr("font-family","sans-serif").attr("text-anchor",t===vt?"start":t===mt?"end":"middle"),G.each(function(){this.__axis=P})}return _.scale=function(w){return arguments.length?(e=w,_):e},_.ticks=function(){return s=Array.from(arguments),_},_.tickArguments=function(w){return arguments.length?(s=w==null?[]:Array.from(w),_):s.slice()},_.tickValues=function(w){return arguments.length?(a=w==null?null:Array.from(w),_):a&&a.slice()},_.tickFormat=function(w){return arguments.length?(r=w,_):r},_.tickSize=function(w){return arguments.length?(h=f=+w,_):h},_.tickSizeInner=function(w){return arguments.length?(h=+w,_):h},_.tickSizeOuter=function(w){return arguments.length?(f=+w,_):f},_.tickPadding=function(w){return arguments.length?(x=+w,_):x},_.offset=function(w){return arguments.length?(C=+w,_):C},_}function ze(t){return Zt(kt,t)}function Oe(t){return Zt(Tt,t)}var Qt={exports:{}};(function(t,e){(function(s,a){t.exports=a()})(St,function(){var s="day";return function(a,r,h){var f=function(v){return v.add(4-v.isoWeekday(),s)},x=r.prototype;x.isoWeekYear=function(){return f(this).year()},x.isoWeek=function(v){if(!this.$utils().u(v))return this.add(7*(v-this.isoWeek()),s);var F,E,_,w,H=f(this),m=(F=this.isoWeekYear(),E=this.$u,_=(E?h.utc:h)().year(F).startOf("year"),w=4-_.isoWeekday(),_.isoWeekday()>4&&(w+=7),_.add(w,s));return H.diff(m,"week")+1},x.isoWeekday=function(v){return this.$utils().u(v)?this.day()||7:this.day(this.day()%7?v:v-7)};var C=x.startOf;x.startOf=function(v,F){var E=this.$utils(),_=!!E.u(F)||F;return E.p(v)==="isoweek"?_?this.date(this.date()-(this.isoWeekday()-1)).startOf("day"):this.date(this.date()-1-(this.isoWeekday()-1)+7).endOf("day"):C.bind(this)(v,F)}}})})(Qt);var Pe=Qt.exports;const Ne=Et(Pe);var Jt={exports:{}};(function(t,e){(function(s,a){t.exports=a()})(St,function(){var s={LTS:"h:mm:ss A",LT:"h:mm A",L:"MM/DD/YYYY",LL:"MMMM D, YYYY",LLL:"MMMM D, YYYY h:mm A",LLLL:"dddd, MMMM D, YYYY h:mm A"},a=/(\[[^[]*\])|([-_:/.,()\s]+)|(A|a|YYYY|YY?|MM?M?M?|Do|DD?|hh?|HH?|mm?|ss?|S{1,3}|z|ZZ?)/g,r=/\d\d/,h=/\d\d?/,f=/\d*[^-_:/,()\s\d]+/,x={},C=function(m){return(m=+m)+(m>68?1900:2e3)},v=function(m){return function(D){this[m]=+D}},F=[/[+-]\d\d:?(\d\d)?|Z/,function(m){(this.zone||(this.zone={})).offset=function(D){if(!D||D==="Z")return 0;var L=D.match(/([+-]|\d\d)/g),M=60*L[1]+(+L[2]||0);return M===0?0:L[0]==="+"?-M:M}(m)}],E=function(m){var D=x[m];return D&&(D.indexOf?D:D.s.concat(D.f))},_=function(m,D){var L,M=x.meridiem;if(M){for(var O=1;O<=24;O+=1)if(m.indexOf(M(O,0,D))>-1){L=O>12;break}}else L=m===(D?"pm":"PM");return L},w={A:[f,function(m){this.afternoon=_(m,!1)}],a:[f,function(m){this.afternoon=_(m,!0)}],S:[/\d/,function(m){this.milliseconds=100*+m}],SS:[r,function(m){this.milliseconds=10*+m}],SSS:[/\d{3}/,function(m){this.milliseconds=+m}],s:[h,v("seconds")],ss:[h,v("seconds")],m:[h,v("minutes")],mm:[h,v("minutes")],H:[h,v("hours")],h:[h,v("hours")],HH:[h,v("hours")],hh:[h,v("hours")],D:[h,v("day")],DD:[r,v("day")],Do:[f,function(m){var D=x.ordinal,L=m.match(/\d+/);if(this.day=L[0],D)for(var M=1;M<=31;M+=1)D(M).replace(/\[|\]/g,"")===m&&(this.day=M)}],M:[h,v("month")],MM:[r,v("month")],MMM:[f,function(m){var D=E("months"),L=(E("monthsShort")||D.map(function(M){return M.slice(0,3)})).indexOf(m)+1;if(L<1)throw new Error;this.month=L%12||L}],MMMM:[f,function(m){var D=E("months").indexOf(m)+1;if(D<1)throw new Error;this.month=D%12||D}],Y:[/[+-]?\d+/,v("year")],YY:[r,function(m){this.year=C(m)}],YYYY:[/\d{4}/,v("year")],Z:F,ZZ:F};function H(m){var D,L;D=m,L=x&&x.formats;for(var M=(m=D.replace(/(\[[^\]]+])|(LTS?|l{1,4}|L{1,4})/g,function(T,g,y){var n=y&&y.toUpperCase();return g||L[y]||s[y]||L[n].replace(/(\[[^\]]+])|(MMMM|MM|DD|dddd)/g,function(u,d,o){return d||o.slice(1)})})).match(a),O=M.length,P=0;P<O;P+=1){var G=M[P],N=w[G],z=N&&N[0],k=N&&N[1];M[P]=k?{regex:z,parser:k}:G.replace(/^\[|\]$/g,"")}return function(T){for(var g={},y=0,n=0;y<O;y+=1){var u=M[y];if(typeof u=="string")n+=u.length;else{var d=u.regex,o=u.parser,p=T.slice(n),i=d.exec(p)[0];o.call(g,i),T=T.replace(i,"")}}return function(W){var c=W.afternoon;if(c!==void 0){var l=W.hours;c?l<12&&(W.hours+=12):l===12&&(W.hours=0),delete W.afternoon}}(g),g}}return function(m,D,L){L.p.customParseFormat=!0,m&&m.parseTwoDigitYear&&(C=m.parseTwoDigitYear);var M=D.prototype,O=M.parse;M.parse=function(P){var G=P.date,N=P.utc,z=P.args;this.$u=N;var k=z[1];if(typeof k=="string"){var T=z[2]===!0,g=z[3]===!0,y=T||g,n=z[2];g&&(n=z[2]),x=this.$locale(),!T&&n&&(x=L.Ls[n]),this.$d=function(p,i,W){try{if(["x","X"].indexOf(i)>-1)return new Date((i==="X"?1e3:1)*p);var c=H(i)(p),l=c.year,b=c.month,V=c.day,A=c.hours,I=c.minutes,S=c.seconds,Y=c.milliseconds,tt=c.zone,Q=new Date,at=V||(l||b?1:Q.getDate()),ot=l||Q.getFullYear(),B=0;l&&!b||(B=b>0?b-1:Q.getMonth());var q=A||0,X=I||0,et=S||0,U=Y||0;return tt?new Date(Date.UTC(ot,B,at,q,X,et,U+60*tt.offset*1e3)):W?new Date(Date.UTC(ot,B,at,q,X,et,U)):new Date(ot,B,at,q,X,et,U)}catch{return new Date("")}}(G,k,N),this.init(),n&&n!==!0&&(this.$L=this.locale(n).$L),y&&G!=this.format(k)&&(this.$d=new Date("")),x={}}else if(k instanceof Array)for(var u=k.length,d=1;d<=u;d+=1){z[1]=k[d-1];var o=L.apply(this,z);if(o.isValid()){this.$d=o.$d,this.$L=o.$L,this.init();break}d===u&&(this.$d=new Date(""))}else O.call(this,P)}}})})(Jt);var Be=Jt.exports;const Re=Et(Be);var Kt={exports:{}};(function(t,e){(function(s,a){t.exports=a()})(St,function(){return function(s,a){var r=a.prototype,h=r.format;r.format=function(f){var x=this,C=this.$locale();if(!this.isValid())return h.bind(this)(f);var v=this.$utils(),F=(f||"YYYY-MM-DDTHH:mm:ssZ").replace(/\[([^\]]+)]|Q|wo|ww|w|WW|W|zzz|z|gggg|GGGG|Do|X|x|k{1,2}|S/g,function(E){switch(E){case"Q":return Math.ceil((x.$M+1)/3);case"Do":return C.ordinal(x.$D);case"gggg":return x.weekYear();case"GGGG":return x.isoWeekYear();case"wo":return C.ordinal(x.week(),"W");case"w":case"ww":return v.s(x.week(),E==="w"?1:2,"0");case"W":case"WW":return v.s(x.isoWeek(),E==="W"?1:2,"0");case"k":case"kk":return v.s(String(x.$H===0?24:x.$H),E==="k"?1:2,"0");case"X":return Math.floor(x.$d.getTime()/1e3);case"x":return x.$d.getTime();case"z":return"["+x.offsetName()+"]";case"zzz":return"["+x.offsetName("long")+"]";default:return E}});return h.bind(this)(F)}}})})(Kt);var He=Kt.exports;const Ge=Et(He);var wt=function(){var t=function(y,n,u,d){for(u=u||{},d=y.length;d--;u[y[d]]=n);return u},e=[6,8,10,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,30,32,33,35,37],s=[1,25],a=[1,26],r=[1,27],h=[1,28],f=[1,29],x=[1,30],C=[1,31],v=[1,9],F=[1,10],E=[1,11],_=[1,12],w=[1,13],H=[1,14],m=[1,15],D=[1,16],L=[1,18],M=[1,19],O=[1,20],P=[1,21],G=[1,22],N=[1,24],z=[1,32],k={trace:function(){},yy:{},symbols_:{error:2,start:3,gantt:4,document:5,EOF:6,line:7,SPACE:8,statement:9,NL:10,weekday:11,weekday_monday:12,weekday_tuesday:13,weekday_wednesday:14,weekday_thursday:15,weekday_friday:16,weekday_saturday:17,weekday_sunday:18,dateFormat:19,inclusiveEndDates:20,topAxis:21,axisFormat:22,tickInterval:23,excludes:24,includes:25,todayMarker:26,title:27,acc_title:28,acc_title_value:29,acc_descr:30,acc_descr_value:31,acc_descr_multiline_value:32,section:33,clickStatement:34,taskTxt:35,taskData:36,click:37,callbackname:38,callbackargs:39,href:40,clickStatementDebug:41,$accept:0,$end:1},terminals_:{2:"error",4:"gantt",6:"EOF",8:"SPACE",10:"NL",12:"weekday_monday",13:"weekday_tuesday",14:"weekday_wednesday",15:"weekday_thursday",16:"weekday_friday",17:"weekday_saturday",18:"weekday_sunday",19:"dateFormat",20:"inclusiveEndDates",21:"topAxis",22:"axisFormat",23:"tickInterval",24:"excludes",25:"includes",26:"todayMarker",27:"title",28:"acc_title",29:"acc_title_value",30:"acc_descr",31:"acc_descr_value",32:"acc_descr_multiline_value",33:"section",35:"taskTxt",36:"taskData",37:"click",38:"callbackname",39:"callbackargs",40:"href"},productions_:[0,[3,3],[5,0],[5,2],[7,2],[7,1],[7,1],[7,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[11,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,1],[9,2],[9,2],[9,1],[9,1],[9,1],[9,2],[34,2],[34,3],[34,3],[34,4],[34,3],[34,4],[34,2],[41,2],[41,3],[41,3],[41,4],[41,3],[41,4],[41,2]],performAction:function(n,u,d,o,p,i,W){var c=i.length-1;switch(p){case 1:return i[c-1];case 2:this.$=[];break;case 3:i[c-1].push(i[c]),this.$=i[c-1];break;case 4:case 5:this.$=i[c];break;case 6:case 7:this.$=[];break;case 8:o.setWeekday("monday");break;case 9:o.setWeekday("tuesday");break;case 10:o.setWeekday("wednesday");break;case 11:o.setWeekday("thursday");break;case 12:o.setWeekday("friday");break;case 13:o.setWeekday("saturday");break;case 14:o.setWeekday("sunday");break;case 15:o.setDateFormat(i[c].substr(11)),this.$=i[c].substr(11);break;case 16:o.enableInclusiveEndDates(),this.$=i[c].substr(18);break;case 17:o.TopAxis(),this.$=i[c].substr(8);break;case 18:o.setAxisFormat(i[c].substr(11)),this.$=i[c].substr(11);break;case 19:o.setTickInterval(i[c].substr(13)),this.$=i[c].substr(13);break;case 20:o.setExcludes(i[c].substr(9)),this.$=i[c].substr(9);break;case 21:o.setIncludes(i[c].substr(9)),this.$=i[c].substr(9);break;case 22:o.setTodayMarker(i[c].substr(12)),this.$=i[c].substr(12);break;case 24:o.setDiagramTitle(i[c].substr(6)),this.$=i[c].substr(6);break;case 25:this.$=i[c].trim(),o.setAccTitle(this.$);break;case 26:case 27:this.$=i[c].trim(),o.setAccDescription(this.$);break;case 28:o.addSection(i[c].substr(8)),this.$=i[c].substr(8);break;case 30:o.addTask(i[c-1],i[c]),this.$="task";break;case 31:this.$=i[c-1],o.setClickEvent(i[c-1],i[c],null);break;case 32:this.$=i[c-2],o.setClickEvent(i[c-2],i[c-1],i[c]);break;case 33:this.$=i[c-2],o.setClickEvent(i[c-2],i[c-1],null),o.setLink(i[c-2],i[c]);break;case 34:this.$=i[c-3],o.setClickEvent(i[c-3],i[c-2],i[c-1]),o.setLink(i[c-3],i[c]);break;case 35:this.$=i[c-2],o.setClickEvent(i[c-2],i[c],null),o.setLink(i[c-2],i[c-1]);break;case 36:this.$=i[c-3],o.setClickEvent(i[c-3],i[c-1],i[c]),o.setLink(i[c-3],i[c-2]);break;case 37:this.$=i[c-1],o.setLink(i[c-1],i[c]);break;case 38:case 44:this.$=i[c-1]+" "+i[c];break;case 39:case 40:case 42:this.$=i[c-2]+" "+i[c-1]+" "+i[c];break;case 41:case 43:this.$=i[c-3]+" "+i[c-2]+" "+i[c-1]+" "+i[c];break}},table:[{3:1,4:[1,2]},{1:[3]},t(e,[2,2],{5:3}),{6:[1,4],7:5,8:[1,6],9:7,10:[1,8],11:17,12:s,13:a,14:r,15:h,16:f,17:x,18:C,19:v,20:F,21:E,22:_,23:w,24:H,25:m,26:D,27:L,28:M,30:O,32:P,33:G,34:23,35:N,37:z},t(e,[2,7],{1:[2,1]}),t(e,[2,3]),{9:33,11:17,12:s,13:a,14:r,15:h,16:f,17:x,18:C,19:v,20:F,21:E,22:_,23:w,24:H,25:m,26:D,27:L,28:M,30:O,32:P,33:G,34:23,35:N,37:z},t(e,[2,5]),t(e,[2,6]),t(e,[2,15]),t(e,[2,16]),t(e,[2,17]),t(e,[2,18]),t(e,[2,19]),t(e,[2,20]),t(e,[2,21]),t(e,[2,22]),t(e,[2,23]),t(e,[2,24]),{29:[1,34]},{31:[1,35]},t(e,[2,27]),t(e,[2,28]),t(e,[2,29]),{36:[1,36]},t(e,[2,8]),t(e,[2,9]),t(e,[2,10]),t(e,[2,11]),t(e,[2,12]),t(e,[2,13]),t(e,[2,14]),{38:[1,37],40:[1,38]},t(e,[2,4]),t(e,[2,25]),t(e,[2,26]),t(e,[2,30]),t(e,[2,31],{39:[1,39],40:[1,40]}),t(e,[2,37],{38:[1,41]}),t(e,[2,32],{40:[1,42]}),t(e,[2,33]),t(e,[2,35],{39:[1,43]}),t(e,[2,34]),t(e,[2,36])],defaultActions:{},parseError:function(n,u){if(u.recoverable)this.trace(n);else{var d=new Error(n);throw d.hash=u,d}},parse:function(n){var u=this,d=[0],o=[],p=[null],i=[],W=this.table,c="",l=0,b=0,V=2,A=1,I=i.slice.call(arguments,1),S=Object.create(this.lexer),Y={yy:{}};for(var tt in this.yy)Object.prototype.hasOwnProperty.call(this.yy,tt)&&(Y.yy[tt]=this.yy[tt]);S.setInput(n,Y.yy),Y.yy.lexer=S,Y.yy.parser=this,typeof S.yylloc>"u"&&(S.yylloc={});var Q=S.yylloc;i.push(Q);var at=S.options&&S.options.ranges;typeof Y.yy.parseError=="function"?this.parseError=Y.yy.parseError:this.parseError=Object.getPrototypeOf(this).parseError;function ot(){var K;return K=o.pop()||S.lex()||A,typeof K!="number"&&(K instanceof Array&&(o=K,K=o.pop()),K=u.symbols_[K]||K),K}for(var B,q,X,et,U={},ct,J,Ot,ft;;){if(q=d[d.length-1],this.defaultActions[q]?X=this.defaultActions[q]:((B===null||typeof B>"u")&&(B=ot()),X=W[q]&&W[q][B]),typeof X>"u"||!X.length||!X[0]){var xt="";ft=[];for(ct in W[q])this.terminals_[ct]&&ct>V&&ft.push("'"+this.terminals_[ct]+"'");S.showPosition?xt="Parse error on line "+(l+1)+`:
`+S.showPosition()+`
Expecting `+ft.join(", ")+", got '"+(this.terminals_[B]||B)+"'":xt="Parse error on line "+(l+1)+": Unexpected "+(B==A?"end of input":"'"+(this.terminals_[B]||B)+"'"),this.parseError(xt,{text:S.match,token:this.terminals_[B]||B,line:S.yylineno,loc:Q,expected:ft})}if(X[0]instanceof Array&&X.length>1)throw new Error("Parse Error: multiple actions possible at state: "+q+", token: "+B);switch(X[0]){case 1:d.push(B),p.push(S.yytext),i.push(S.yylloc),d.push(X[1]),B=null,b=S.yyleng,c=S.yytext,l=S.yylineno,Q=S.yylloc;break;case 2:if(J=this.productions_[X[1]][1],U.$=p[p.length-J],U._$={first_line:i[i.length-(J||1)].first_line,last_line:i[i.length-1].last_line,first_column:i[i.length-(J||1)].first_column,last_column:i[i.length-1].last_column},at&&(U._$.range=[i[i.length-(J||1)].range[0],i[i.length-1].range[1]]),et=this.performAction.apply(U,[c,b,l,Y.yy,X[1],p,i].concat(I)),typeof et<"u")return et;J&&(d=d.slice(0,-1*J*2),p=p.slice(0,-1*J),i=i.slice(0,-1*J)),d.push(this.productions_[X[1]][0]),p.push(U.$),i.push(U._$),Ot=W[d[d.length-2]][d[d.length-1]],d.push(Ot);break;case 3:return!0}}return!0}},T=function(){var y={EOF:1,parseError:function(u,d){if(this.yy.parser)this.yy.parser.parseError(u,d);else throw new Error(u)},setInput:function(n,u){return this.yy=u||this.yy||{},this._input=n,this._more=this._backtrack=this.done=!1,this.yylineno=this.yyleng=0,this.yytext=this.matched=this.match="",this.conditionStack=["INITIAL"],this.yylloc={first_line:1,first_column:0,last_line:1,last_column:0},this.options.ranges&&(this.yylloc.range=[0,0]),this.offset=0,this},input:function(){var n=this._input[0];this.yytext+=n,this.yyleng++,this.offset++,this.match+=n,this.matched+=n;var u=n.match(/(?:\r\n?|\n).*/g);return u?(this.yylineno++,this.yylloc.last_line++):this.yylloc.last_column++,this.options.ranges&&this.yylloc.range[1]++,this._input=this._input.slice(1),n},unput:function(n){var u=n.length,d=n.split(/(?:\r\n?|\n)/g);this._input=n+this._input,this.yytext=this.yytext.substr(0,this.yytext.length-u),this.offset-=u;var o=this.match.split(/(?:\r\n?|\n)/g);this.match=this.match.substr(0,this.match.length-1),this.matched=this.matched.substr(0,this.matched.length-1),d.length-1&&(this.yylineno-=d.length-1);var p=this.yylloc.range;return this.yylloc={first_line:this.yylloc.first_line,last_line:this.yylineno+1,first_column:this.yylloc.first_column,last_column:d?(d.length===o.length?this.yylloc.first_column:0)+o[o.length-d.length].length-d[0].length:this.yylloc.first_column-u},this.options.ranges&&(this.yylloc.range=[p[0],p[0]+this.yyleng-u]),this.yyleng=this.yytext.length,this},more:function(){return this._more=!0,this},reject:function(){if(this.options.backtrack_lexer)this._backtrack=!0;else return this.parseError("Lexical error on line "+(this.yylineno+1)+`. You can only invoke reject() in the lexer when the lexer is of the backtracking persuasion (options.backtrack_lexer = true).
`+this.showPosition(),{text:"",token:null,line:this.yylineno});return this},less:function(n){this.unput(this.match.slice(n))},pastInput:function(){var n=this.matched.substr(0,this.matched.length-this.match.length);return(n.length>20?"...":"")+n.substr(-20).replace(/\n/g,"")},upcomingInput:function(){var n=this.match;return n.length<20&&(n+=this._input.substr(0,20-n.length)),(n.substr(0,20)+(n.length>20?"...":"")).replace(/\n/g,"")},showPosition:function(){var n=this.pastInput(),u=new Array(n.length+1).join("-");return n+this.upcomingInput()+`
`+u+"^"},test_match:function(n,u){var d,o,p;if(this.options.backtrack_lexer&&(p={yylineno:this.yylineno,yylloc:{first_line:this.yylloc.first_line,last_line:this.last_line,first_column:this.yylloc.first_column,last_column:this.yylloc.last_column},yytext:this.yytext,match:this.match,matches:this.matches,matched:this.matched,yyleng:this.yyleng,offset:this.offset,_more:this._more,_input:this._input,yy:this.yy,conditionStack:this.conditionStack.slice(0),done:this.done},this.options.ranges&&(p.yylloc.range=this.yylloc.range.slice(0))),o=n[0].match(/(?:\r\n?|\n).*/g),o&&(this.yylineno+=o.length),this.yylloc={first_line:this.yylloc.last_line,last_line:this.yylineno+1,first_column:this.yylloc.last_column,last_column:o?o[o.length-1].length-o[o.length-1].match(/\r?\n?/)[0].length:this.yylloc.last_column+n[0].length},this.yytext+=n[0],this.match+=n[0],this.matches=n,this.yyleng=this.yytext.length,this.options.ranges&&(this.yylloc.range=[this.offset,this.offset+=this.yyleng]),this._more=!1,this._backtrack=!1,this._input=this._input.slice(n[0].length),this.matched+=n[0],d=this.performAction.call(this,this.yy,this,u,this.conditionStack[this.conditionStack.length-1]),this.done&&this._input&&(this.done=!1),d)return d;if(this._backtrack){for(var i in p)this[i]=p[i];return!1}return!1},next:function(){if(this.done)return this.EOF;this._input||(this.done=!0);var n,u,d,o;this._more||(this.yytext="",this.match="");for(var p=this._currentRules(),i=0;i<p.length;i++)if(d=this._input.match(this.rules[p[i]]),d&&(!u||d[0].length>u[0].length)){if(u=d,o=i,this.options.backtrack_lexer){if(n=this.test_match(d,p[i]),n!==!1)return n;if(this._backtrack){u=!1;continue}else return!1}else if(!this.options.flex)break}return u?(n=this.test_match(u,p[o]),n!==!1?n:!1):this._input===""?this.EOF:this.parseError("Lexical error on line "+(this.yylineno+1)+`. Unrecognized text.
`+this.showPosition(),{text:"",token:null,line:this.yylineno})},lex:function(){var u=this.next();return u||this.lex()},begin:function(u){this.conditionStack.push(u)},popState:function(){var u=this.conditionStack.length-1;return u>0?this.conditionStack.pop():this.conditionStack[0]},_currentRules:function(){return this.conditionStack.length&&this.conditionStack[this.conditionStack.length-1]?this.conditions[this.conditionStack[this.conditionStack.length-1]].rules:this.conditions.INITIAL.rules},topState:function(u){return u=this.conditionStack.length-1-Math.abs(u||0),u>=0?this.conditionStack[u]:"INITIAL"},pushState:function(u){this.begin(u)},stateStackSize:function(){return this.conditionStack.length},options:{"case-insensitive":!0},performAction:function(u,d,o,p){switch(o){case 0:return this.begin("open_directive"),"open_directive";case 1:return this.begin("acc_title"),28;case 2:return this.popState(),"acc_title_value";case 3:return this.begin("acc_descr"),30;case 4:return this.popState(),"acc_descr_value";case 5:this.begin("acc_descr_multiline");break;case 6:this.popState();break;case 7:return"acc_descr_multiline_value";case 8:break;case 9:break;case 10:break;case 11:return 10;case 12:break;case 13:break;case 14:this.begin("href");break;case 15:this.popState();break;case 16:return 40;case 17:this.begin("callbackname");break;case 18:this.popState();break;case 19:this.popState(),this.begin("callbackargs");break;case 20:return 38;case 21:this.popState();break;case 22:return 39;case 23:this.begin("click");break;case 24:this.popState();break;case 25:return 37;case 26:return 4;case 27:return 19;case 28:return 20;case 29:return 21;case 30:return 22;case 31:return 23;case 32:return 25;case 33:return 24;case 34:return 26;case 35:return 12;case 36:return 13;case 37:return 14;case 38:return 15;case 39:return 16;case 40:return 17;case 41:return 18;case 42:return"date";case 43:return 27;case 44:return"accDescription";case 45:return 33;case 46:return 35;case 47:return 36;case 48:return":";case 49:return 6;case 50:return"INVALID"}},rules:[/^(?:%%\{)/i,/^(?:accTitle\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*:\s*)/i,/^(?:(?!\n||)*[^\n]*)/i,/^(?:accDescr\s*\{\s*)/i,/^(?:[\}])/i,/^(?:[^\}]*)/i,/^(?:%%(?!\{)*[^\n]*)/i,/^(?:[^\}]%%*[^\n]*)/i,/^(?:%%*[^\n]*[\n]*)/i,/^(?:[\n]+)/i,/^(?:\s+)/i,/^(?:%[^\n]*)/i,/^(?:href[\s]+["])/i,/^(?:["])/i,/^(?:[^"]*)/i,/^(?:call[\s]+)/i,/^(?:\([\s]*\))/i,/^(?:\()/i,/^(?:[^(]*)/i,/^(?:\))/i,/^(?:[^)]*)/i,/^(?:click[\s]+)/i,/^(?:[\s\n])/i,/^(?:[^\s\n]*)/i,/^(?:gantt\b)/i,/^(?:dateFormat\s[^#\n;]+)/i,/^(?:inclusiveEndDates\b)/i,/^(?:topAxis\b)/i,/^(?:axisFormat\s[^#\n;]+)/i,/^(?:tickInterval\s[^#\n;]+)/i,/^(?:includes\s[^#\n;]+)/i,/^(?:excludes\s[^#\n;]+)/i,/^(?:todayMarker\s[^\n;]+)/i,/^(?:weekday\s+monday\b)/i,/^(?:weekday\s+tuesday\b)/i,/^(?:weekday\s+wednesday\b)/i,/^(?:weekday\s+thursday\b)/i,/^(?:weekday\s+friday\b)/i,/^(?:weekday\s+saturday\b)/i,/^(?:weekday\s+sunday\b)/i,/^(?:\d\d\d\d-\d\d-\d\d\b)/i,/^(?:title\s[^\n]+)/i,/^(?:accDescription\s[^#\n;]+)/i,/^(?:section\s[^\n]+)/i,/^(?:[^:\n]+)/i,/^(?::[^#\n;]+)/i,/^(?::)/i,/^(?:$)/i,/^(?:.)/i],conditions:{acc_descr_multiline:{rules:[6,7],inclusive:!1},acc_descr:{rules:[4],inclusive:!1},acc_title:{rules:[2],inclusive:!1},callbackargs:{rules:[21,22],inclusive:!1},callbackname:{rules:[18,19,20],inclusive:!1},href:{rules:[15,16],inclusive:!1},click:{rules:[24,25],inclusive:!1},INITIAL:{rules:[0,1,3,5,8,9,10,11,12,13,14,17,23,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50],inclusive:!0}}};return y}();k.lexer=T;function g(){this.yy={}}return g.prototype=k,k.Parser=g,new g}();wt.parser=wt;const Xe=wt;j.extend(Ne);j.extend(Re);j.extend(Ge);let Z="",At="",Mt,Lt="",lt=[],ut=[],It={},Yt=[],bt=[],st="",Ft="";const $t=["active","done","crit","milestone"];let Wt=[],dt=!1,Vt=!1,zt="sunday",_t=0;const je=function(){Yt=[],bt=[],st="",Wt=[],yt=0,Ct=void 0,gt=void 0,R=[],Z="",At="",Ft="",Mt=void 0,Lt="",lt=[],ut=[],dt=!1,Vt=!1,_t=0,It={},me(),zt="sunday"},qe=function(t){At=t},Ue=function(){return At},Ze=function(t){Mt=t},Qe=function(){return Mt},Je=function(t){Lt=t},Ke=function(){return Lt},$e=function(t){Z=t},tn=function(){dt=!0},en=function(){return dt},nn=function(){Vt=!0},sn=function(){return Vt},rn=function(t){Ft=t},an=function(){return Ft},on=function(){return Z},cn=function(t){lt=t.toLowerCase().split(/[\s,]+/)},ln=function(){return lt},un=function(t){ut=t.toLowerCase().split(/[\s,]+/)},dn=function(){return ut},fn=function(){return It},hn=function(t){st=t,Yt.push(t)},mn=function(){return Yt},kn=function(){let t=qt();const e=10;let s=0;for(;!t&&s<e;)t=qt(),s++;return bt=R,bt},te=function(t,e,s,a){return a.includes(t.format(e.trim()))?!1:t.isoWeekday()>=6&&s.includes("weekends")||s.includes(t.format("dddd").toLowerCase())?!0:s.includes(t.format(e.trim()))},yn=function(t){zt=t},gn=function(){return zt},ee=function(t,e,s,a){if(!s.length||t.manualEndTime)return;let r;t.startTime instanceof Date?r=j(t.startTime):r=j(t.startTime,e,!0),r=r.add(1,"d");let h;t.endTime instanceof Date?h=j(t.endTime):h=j(t.endTime,e,!0);const[f,x]=pn(r,h,e,s,a);t.endTime=f.toDate(),t.renderEndTime=x},pn=function(t,e,s,a,r){let h=!1,f=null;for(;t<=e;)h||(f=e.toDate()),h=te(t,s,a,r),h&&(e=e.add(1,"d")),t=t.add(1,"d");return[e,f]},Dt=function(t,e,s){s=s.trim();const r=/^after\s+([\d\w- ]+)/.exec(s.trim());if(r!==null){let f=null;if(r[1].split(" ").forEach(function(x){let C=rt(x);C!==void 0&&(f?C.endTime>f.endTime&&(f=C):f=C)}),f)return f.endTime;{const x=new Date;return x.setHours(0,0,0,0),x}}let h=j(s,e.trim(),!0);if(h.isValid())return h.toDate();{pt.debug("Invalid date:"+s),pt.debug("With date format:"+e.trim());const f=new Date(s);if(f===void 0||isNaN(f.getTime())||f.getFullYear()<-1e4||f.getFullYear()>1e4)throw new Error("Invalid date:"+s);return f}},ne=function(t){const e=/^(\d+(?:\.\d+)?)([Mdhmswy]|ms)$/.exec(t.trim());return e!==null?[Number.parseFloat(e[1]),e[2]]:[NaN,"ms"]},ie=function(t,e,s,a=!1){s=s.trim();let r=j(s,e.trim(),!0);if(r.isValid())return a&&(r=r.add(1,"d")),r.toDate();let h=j(t);const[f,x]=ne(s);if(!Number.isNaN(f)){const C=h.add(f,x);C.isValid()&&(h=C)}return h.toDate()};let yt=0;const it=function(t){return t===void 0?(yt=yt+1,"task"+yt):t},bn=function(t,e){let s;e.substr(0,1)===":"?s=e.substr(1,e.length):s=e;const a=s.split(","),r={};oe(a,r,$t);for(let f=0;f<a.length;f++)a[f]=a[f].trim();let h="";switch(a.length){case 1:r.id=it(),r.startTime=t.endTime,h=a[0];break;case 2:r.id=it(),r.startTime=Dt(void 0,Z,a[0]),h=a[1];break;case 3:r.id=it(a[0]),r.startTime=Dt(void 0,Z,a[1]),h=a[2];break}return h&&(r.endTime=ie(r.startTime,Z,h,dt),r.manualEndTime=j(h,"YYYY-MM-DD",!0).isValid(),ee(r,Z,ut,lt)),r},xn=function(t,e){let s;e.substr(0,1)===":"?s=e.substr(1,e.length):s=e;const a=s.split(","),r={};oe(a,r,$t);for(let h=0;h<a.length;h++)a[h]=a[h].trim();switch(a.length){case 1:r.id=it(),r.startTime={type:"prevTaskEnd",id:t},r.endTime={data:a[0]};break;case 2:r.id=it(),r.startTime={type:"getStartDate",startData:a[0]},r.endTime={data:a[1]};break;case 3:r.id=it(a[0]),r.startTime={type:"getStartDate",startData:a[1]},r.endTime={data:a[2]};break}return r};let Ct,gt,R=[];const se={},vn=function(t,e){const s={section:st,type:st,processed:!1,manualEndTime:!1,renderEndTime:null,raw:{data:e},task:t,classes:[]},a=xn(gt,e);s.raw.startTime=a.startTime,s.raw.endTime=a.endTime,s.id=a.id,s.prevTaskId=gt,s.active=a.active,s.done=a.done,s.crit=a.crit,s.milestone=a.milestone,s.order=_t,_t++;const r=R.push(s);gt=s.id,se[s.id]=r-1},rt=function(t){const e=se[t];return R[e]},Tn=function(t,e){const s={section:st,type:st,description:t,task:t,classes:[]},a=bn(Ct,e);s.startTime=a.startTime,s.endTime=a.endTime,s.id=a.id,s.active=a.active,s.done=a.done,s.crit=a.crit,s.milestone=a.milestone,Ct=s,bt.push(s)},qt=function(){const t=function(s){const a=R[s];let r="";switch(R[s].raw.startTime.type){case"prevTaskEnd":{const h=rt(a.prevTaskId);a.startTime=h.endTime;break}case"getStartDate":r=Dt(void 0,Z,R[s].raw.startTime.startData),r&&(R[s].startTime=r);break}return R[s].startTime&&(R[s].endTime=ie(R[s].startTime,Z,R[s].raw.endTime.data,dt),R[s].endTime&&(R[s].processed=!0,R[s].manualEndTime=j(R[s].raw.endTime.data,"YYYY-MM-DD",!0).isValid(),ee(R[s],Z,ut,lt))),R[s].processed};let e=!0;for(const[s,a]of R.entries())t(s),e=e&&a.processed;return e},wn=function(t,e){let s=e;nt().securityLevel!=="loose"&&(s=ke.sanitizeUrl(e)),t.split(",").forEach(function(a){rt(a)!==void 0&&(ae(a,()=>{window.open(s,"_self")}),It[a]=s)}),re(t,"clickable")},re=function(t,e){t.split(",").forEach(function(s){let a=rt(s);a!==void 0&&a.classes.push(e)})},_n=function(t,e,s){if(nt().securityLevel!=="loose"||e===void 0)return;let a=[];if(typeof s=="string"){a=s.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);for(let h=0;h<a.length;h++){let f=a[h].trim();f.charAt(0)==='"'&&f.charAt(f.length-1)==='"'&&(f=f.substr(1,f.length-2)),a[h]=f}}a.length===0&&a.push(t),rt(t)!==void 0&&ae(t,()=>{pe.runFunc(e,...a)})},ae=function(t,e){Wt.push(function(){const s=document.querySelector(`[id="${t}"]`);s!==null&&s.addEventListener("click",function(){e()})},function(){const s=document.querySelector(`[id="${t}-text"]`);s!==null&&s.addEventListener("click",function(){e()})})},Dn=function(t,e,s){t.split(",").forEach(function(a){_n(a,e,s)}),re(t,"clickable")},Cn=function(t){Wt.forEach(function(e){e(t)})},Sn={getConfig:()=>nt().gantt,clear:je,setDateFormat:$e,getDateFormat:on,enableInclusiveEndDates:tn,endDatesAreInclusive:en,enableTopAxis:nn,topAxisEnabled:sn,setAxisFormat:qe,getAxisFormat:Ue,setTickInterval:Ze,getTickInterval:Qe,setTodayMarker:Je,getTodayMarker:Ke,setAccTitle:ce,getAccTitle:le,setDiagramTitle:ue,getDiagramTitle:de,setDisplayMode:rn,getDisplayMode:an,setAccDescription:fe,getAccDescription:he,addSection:hn,getSections:mn,getTasks:kn,addTask:vn,findTaskById:rt,addTaskOrg:Tn,setIncludes:cn,getIncludes:ln,setExcludes:un,getExcludes:dn,setClickEvent:Dn,setLink:wn,getLinks:fn,bindFunctions:Cn,parseDuration:ne,isInvalidDate:te,setWeekday:yn,getWeekday:gn};function oe(t,e,s){let a=!0;for(;a;)a=!1,s.forEach(function(r){const h="^\\s*"+r+"\\s*$",f=new RegExp(h);t[0].match(f)&&(e[r]=!0,t.shift(1),a=!0)})}const En=function(){pt.debug("Something is calling, setConf, remove the call")},Ut={monday:_e,tuesday:De,wednesday:Ce,thursday:Se,friday:Ee,saturday:Ae,sunday:Me},An=(t,e)=>{let s=[...t].map(()=>-1/0),a=[...t].sort((h,f)=>h.startTime-f.startTime||h.order-f.order),r=0;for(const h of a)for(let f=0;f<s.length;f++)if(h.startTime>=s[f]){s[f]=h.endTime,h.order=f+e,f>r&&(r=f);break}return r};let $;const Mn=function(t,e,s,a){const r=nt().gantt,h=nt().securityLevel;let f;h==="sandbox"&&(f=ht("#i"+e));const x=h==="sandbox"?ht(f.nodes()[0].contentDocument.body):ht("body"),C=h==="sandbox"?f.nodes()[0].contentDocument:document,v=C.getElementById(e);$=v.parentElement.offsetWidth,$===void 0&&($=1200),r.useWidth!==void 0&&($=r.useWidth);const F=a.db.getTasks();let E=[];for(const k of F)E.push(k.type);E=z(E);const _={};let w=2*r.topPadding;if(a.db.getDisplayMode()==="compact"||r.displayMode==="compact"){const k={};for(const g of F)k[g.section]===void 0?k[g.section]=[g]:k[g.section].push(g);let T=0;for(const g of Object.keys(k)){const y=An(k[g],T)+1;T+=y,w+=y*(r.barHeight+r.barGap),_[g]=y}}else{w+=F.length*(r.barHeight+r.barGap);for(const k of E)_[k]=F.filter(T=>T.type===k).length}v.setAttribute("viewBox","0 0 "+$+" "+w);const H=x.select(`[id="${e}"]`),m=be().domain([xe(F,function(k){return k.startTime}),ve(F,function(k){return k.endTime})]).rangeRound([0,$-r.leftPadding-r.rightPadding]);function D(k,T){const g=k.startTime,y=T.startTime;let n=0;return g>y?n=1:g<y&&(n=-1),n}F.sort(D),L(F,$,w),ye(H,w,$,r.useMaxWidth),H.append("text").text(a.db.getDiagramTitle()).attr("x",$/2).attr("y",r.titleTopMargin).attr("class","titleText");function L(k,T,g){const y=r.barHeight,n=y+r.barGap,u=r.topPadding,d=r.leftPadding,o=Te().domain([0,E.length]).range(["#00B9FA","#F95002"]).interpolate(we);O(n,u,d,T,g,k,a.db.getExcludes(),a.db.getIncludes()),P(d,u,T,g),M(k,n,u,d,y,o,T),G(n,u),N(d,u,T,g)}function M(k,T,g,y,n,u,d){const p=[...new Set(k.map(l=>l.order))].map(l=>k.find(b=>b.order===l));H.append("g").selectAll("rect").data(p).enter().append("rect").attr("x",0).attr("y",function(l,b){return b=l.order,b*T+g-2}).attr("width",function(){return d-r.rightPadding/2}).attr("height",T).attr("class",function(l){for(const[b,V]of E.entries())if(l.type===V)return"section section"+b%r.numberSectionStyles;return"section section0"});const i=H.append("g").selectAll("rect").data(k).enter(),W=a.db.getLinks();if(i.append("rect").attr("id",function(l){return l.id}).attr("rx",3).attr("ry",3).attr("x",function(l){return l.milestone?m(l.startTime)+y+.5*(m(l.endTime)-m(l.startTime))-.5*n:m(l.startTime)+y}).attr("y",function(l,b){return b=l.order,b*T+g}).attr("width",function(l){return l.milestone?n:m(l.renderEndTime||l.endTime)-m(l.startTime)}).attr("height",n).attr("transform-origin",function(l,b){return b=l.order,(m(l.startTime)+y+.5*(m(l.endTime)-m(l.startTime))).toString()+"px "+(b*T+g+.5*n).toString()+"px"}).attr("class",function(l){const b="task";let V="";l.classes.length>0&&(V=l.classes.join(" "));let A=0;for(const[S,Y]of E.entries())l.type===Y&&(A=S%r.numberSectionStyles);let I="";return l.active?l.crit?I+=" activeCrit":I=" active":l.done?l.crit?I=" doneCrit":I=" done":l.crit&&(I+=" crit"),I.length===0&&(I=" task"),l.milestone&&(I=" milestone "+I),I+=A,I+=" "+V,b+I}),i.append("text").attr("id",function(l){return l.id+"-text"}).text(function(l){return l.task}).attr("font-size",r.fontSize).attr("x",function(l){let b=m(l.startTime),V=m(l.renderEndTime||l.endTime);l.milestone&&(b+=.5*(m(l.endTime)-m(l.startTime))-.5*n),l.milestone&&(V=b+n);const A=this.getBBox().width;return A>V-b?V+A+1.5*r.leftPadding>d?b+y-5:V+y+5:(V-b)/2+b+y}).attr("y",function(l,b){return b=l.order,b*T+r.barHeight/2+(r.fontSize/2-2)+g}).attr("text-height",n).attr("class",function(l){const b=m(l.startTime);let V=m(l.endTime);l.milestone&&(V=b+n);const A=this.getBBox().width;let I="";l.classes.length>0&&(I=l.classes.join(" "));let S=0;for(const[tt,Q]of E.entries())l.type===Q&&(S=tt%r.numberSectionStyles);let Y="";return l.active&&(l.crit?Y="activeCritText"+S:Y="activeText"+S),l.done?l.crit?Y=Y+" doneCritText"+S:Y=Y+" doneText"+S:l.crit&&(Y=Y+" critText"+S),l.milestone&&(Y+=" milestoneText"),A>V-b?V+A+1.5*r.leftPadding>d?I+" taskTextOutsideLeft taskTextOutside"+S+" "+Y:I+" taskTextOutsideRight taskTextOutside"+S+" "+Y+" width-"+A:I+" taskText taskText"+S+" "+Y+" width-"+A}),nt().securityLevel==="sandbox"){let l;l=ht("#i"+e);const b=l.nodes()[0].contentDocument;i.filter(function(V){return W[V.id]!==void 0}).each(function(V){var A=b.querySelector("#"+V.id),I=b.querySelector("#"+V.id+"-text");const S=A.parentNode;var Y=b.createElement("a");Y.setAttribute("xlink:href",W[V.id]),Y.setAttribute("target","_top"),S.appendChild(Y),Y.appendChild(A),Y.appendChild(I)})}}function O(k,T,g,y,n,u,d,o){if(d.length===0&&o.length===0)return;let p,i;for(const{startTime:A,endTime:I}of u)(p===void 0||A<p)&&(p=A),(i===void 0||I>i)&&(i=I);if(!p||!i)return;if(j(i).diff(j(p),"year")>5){pt.warn("The difference between the min and max time is more than 5 years. This will cause performance issues. Skipping drawing exclude days.");return}const W=a.db.getDateFormat(),c=[];let l=null,b=j(p);for(;b.valueOf()<=i;)a.db.isInvalidDate(b,W,d,o)?l?l.end=b:l={start:b,end:b}:l&&(c.push(l),l=null),b=b.add(1,"d");H.append("g").selectAll("rect").data(c).enter().append("rect").attr("id",function(A){return"exclude-"+A.start.format("YYYY-MM-DD")}).attr("x",function(A){return m(A.start)+g}).attr("y",r.gridLineStartPadding).attr("width",function(A){const I=A.end.add(1,"day");return m(I)-m(A.start)}).attr("height",n-T-r.gridLineStartPadding).attr("transform-origin",function(A,I){return(m(A.start)+g+.5*(m(A.end)-m(A.start))).toString()+"px "+(I*k+.5*n).toString()+"px"}).attr("class","exclude-range")}function P(k,T,g,y){let n=Oe(m).tickSize(-y+T+r.gridLineStartPadding).tickFormat(Pt(a.db.getAxisFormat()||r.axisFormat||"%Y-%m-%d"));const d=/^([1-9]\d*)(millisecond|second|minute|hour|day|week|month)$/.exec(a.db.getTickInterval()||r.tickInterval);if(d!==null){const o=d[1],p=d[2],i=a.db.getWeekday()||r.weekday;switch(p){case"millisecond":n.ticks(Xt.every(o));break;case"second":n.ticks(Gt.every(o));break;case"minute":n.ticks(Ht.every(o));break;case"hour":n.ticks(Rt.every(o));break;case"day":n.ticks(Bt.every(o));break;case"week":n.ticks(Ut[i].every(o));break;case"month":n.ticks(Nt.every(o));break}}if(H.append("g").attr("class","grid").attr("transform","translate("+k+", "+(y-50)+")").call(n).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10).attr("dy","1em"),a.db.topAxisEnabled()||r.topAxis){let o=ze(m).tickSize(-y+T+r.gridLineStartPadding).tickFormat(Pt(a.db.getAxisFormat()||r.axisFormat||"%Y-%m-%d"));if(d!==null){const p=d[1],i=d[2],W=a.db.getWeekday()||r.weekday;switch(i){case"millisecond":o.ticks(Xt.every(p));break;case"second":o.ticks(Gt.every(p));break;case"minute":o.ticks(Ht.every(p));break;case"hour":o.ticks(Rt.every(p));break;case"day":o.ticks(Bt.every(p));break;case"week":o.ticks(Ut[W].every(p));break;case"month":o.ticks(Nt.every(p));break}}H.append("g").attr("class","grid").attr("transform","translate("+k+", "+T+")").call(o).selectAll("text").style("text-anchor","middle").attr("fill","#000").attr("stroke","none").attr("font-size",10)}}function G(k,T){let g=0;const y=Object.keys(_).map(n=>[n,_[n]]);H.append("g").selectAll("text").data(y).enter().append(function(n){const u=n[0].split(ge.lineBreakRegex),d=-(u.length-1)/2,o=C.createElementNS("http://www.w3.org/2000/svg","text");o.setAttribute("dy",d+"em");for(const[p,i]of u.entries()){const W=C.createElementNS("http://www.w3.org/2000/svg","tspan");W.setAttribute("alignment-baseline","central"),W.setAttribute("x","10"),p>0&&W.setAttribute("dy","1em"),W.textContent=i,o.appendChild(W)}return o}).attr("x",10).attr("y",function(n,u){if(u>0)for(let d=0;d<u;d++)return g+=y[u-1][1],n[1]*k/2+g*k+T;else return n[1]*k/2+T}).attr("font-size",r.sectionFontSize).attr("class",function(n){for(const[u,d]of E.entries())if(n[0]===d)return"sectionTitle sectionTitle"+u%r.numberSectionStyles;return"sectionTitle"})}function N(k,T,g,y){const n=a.db.getTodayMarker();if(n==="off")return;const u=H.append("g").attr("class","today"),d=new Date,o=u.append("line");o.attr("x1",m(d)+k).attr("x2",m(d)+k).attr("y1",r.titleTopMargin).attr("y2",y-r.titleTopMargin).attr("class","today"),n!==""&&o.attr("style",n.replace(/,/g,";"))}function z(k){const T={},g=[];for(let y=0,n=k.length;y<n;++y)Object.prototype.hasOwnProperty.call(T,k[y])||(T[k[y]]=!0,g.push(k[y]));return g}},Ln={setConf:En,draw:Mn},In=t=>`
  .mermaid-main-font {
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }

  .exclude-range {
    fill: ${t.excludeBkgColor};
  }

  .section {
    stroke: none;
    opacity: 0.2;
  }

  .section0 {
    fill: ${t.sectionBkgColor};
  }

  .section2 {
    fill: ${t.sectionBkgColor2};
  }

  .section1,
  .section3 {
    fill: ${t.altSectionBkgColor};
    opacity: 0.2;
  }

  .sectionTitle0 {
    fill: ${t.titleColor};
  }

  .sectionTitle1 {
    fill: ${t.titleColor};
  }

  .sectionTitle2 {
    fill: ${t.titleColor};
  }

  .sectionTitle3 {
    fill: ${t.titleColor};
  }

  .sectionTitle {
    text-anchor: start;
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }


  /* Grid and axis */

  .grid .tick {
    stroke: ${t.gridColor};
    opacity: 0.8;
    shape-rendering: crispEdges;
  }

  .grid .tick text {
    font-family: ${t.fontFamily};
    fill: ${t.textColor};
  }

  .grid path {
    stroke-width: 0;
  }


  /* Today line */

  .today {
    fill: none;
    stroke: ${t.todayLineColor};
    stroke-width: 2px;
  }


  /* Task styling */

  /* Default task */

  .task {
    stroke-width: 2;
  }

  .taskText {
    text-anchor: middle;
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }

  .taskTextOutsideRight {
    fill: ${t.taskTextDarkColor};
    text-anchor: start;
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }

  .taskTextOutsideLeft {
    fill: ${t.taskTextDarkColor};
    text-anchor: end;
  }


  /* Special case clickable */

  .task.clickable {
    cursor: pointer;
  }

  .taskText.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideLeft.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }

  .taskTextOutsideRight.clickable {
    cursor: pointer;
    fill: ${t.taskTextClickableColor} !important;
    font-weight: bold;
  }


  /* Specific task settings for the sections*/

  .taskText0,
  .taskText1,
  .taskText2,
  .taskText3 {
    fill: ${t.taskTextColor};
  }

  .task0,
  .task1,
  .task2,
  .task3 {
    fill: ${t.taskBkgColor};
    stroke: ${t.taskBorderColor};
  }

  .taskTextOutside0,
  .taskTextOutside2
  {
    fill: ${t.taskTextOutsideColor};
  }

  .taskTextOutside1,
  .taskTextOutside3 {
    fill: ${t.taskTextOutsideColor};
  }


  /* Active task */

  .active0,
  .active1,
  .active2,
  .active3 {
    fill: ${t.activeTaskBkgColor};
    stroke: ${t.activeTaskBorderColor};
  }

  .activeText0,
  .activeText1,
  .activeText2,
  .activeText3 {
    fill: ${t.taskTextDarkColor} !important;
  }


  /* Completed task */

  .done0,
  .done1,
  .done2,
  .done3 {
    stroke: ${t.doneTaskBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
  }

  .doneText0,
  .doneText1,
  .doneText2,
  .doneText3 {
    fill: ${t.taskTextDarkColor} !important;
  }


  /* Tasks on the critical line */

  .crit0,
  .crit1,
  .crit2,
  .crit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.critBkgColor};
    stroke-width: 2;
  }

  .activeCrit0,
  .activeCrit1,
  .activeCrit2,
  .activeCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.activeTaskBkgColor};
    stroke-width: 2;
  }

  .doneCrit0,
  .doneCrit1,
  .doneCrit2,
  .doneCrit3 {
    stroke: ${t.critBorderColor};
    fill: ${t.doneTaskBkgColor};
    stroke-width: 2;
    cursor: pointer;
    shape-rendering: crispEdges;
  }

  .milestone {
    transform: rotate(45deg) scale(0.8,0.8);
  }

  .milestoneText {
    font-style: italic;
  }
  .doneCritText0,
  .doneCritText1,
  .doneCritText2,
  .doneCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  .activeCritText0,
  .activeCritText1,
  .activeCritText2,
  .activeCritText3 {
    fill: ${t.taskTextDarkColor} !important;
  }

  .titleText {
    text-anchor: middle;
    font-size: 18px;
    fill: ${t.titleColor||t.textColor};
    font-family: var(--mermaid-font-family, "trebuchet ms", verdana, arial, sans-serif);
  }
`,Yn=In,Vn={parser:Xe,db:Sn,renderer:Ln,styles:Yn};export{Vn as diagram};
