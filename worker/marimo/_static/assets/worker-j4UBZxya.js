var pe=Object.defineProperty;var ye=(y,f,_)=>f in y?pe(y,f,{enumerable:!0,configurable:!0,writable:!0,value:_}):y[f]=_;var g=(y,f,_)=>(ye(y,typeof f!="symbol"?f+"":f,_),_);(function(){"use strict";const y="notebook.py";function f(e){return e.FS}async function _(e){const{pyodide:t,filename:n,code:s,fallbackCode:l}=e,a=f(t),h="/marimo";await a.mkdir(h),await a.mount(t.FS.filesystems.IDBFS,{root:"."},h),await C(t,!0),a.chdir(h);const m=w=>{try{return a.readFile(w,{encoding:"utf8"})}catch{return null}},u=s||l;if(n&&n!==y){const w=m(n);return w?{content:w,filename:n}:(a.writeFile(n,u),{content:u,filename:n})}return a.writeFile(y,u),{content:u,filename:y}}function C(e,t){return new Promise((n,s)=>{f(e).syncfs(t,l=>{if(l){s(l);return}n()})})}const T={debug:(...e)=>{},log:(...e)=>{console.log(...e)},warn:(...e)=>{console.warn(...e)},error:(...e)=>{console.error(...e)}};function J(){return typeof window<"u"&&window.Logger||T}const I=J();function L(e,t){if(!e)throw new Error(t)}class W{constructor(){g(this,"pyodide",null)}async bootstrap(t){const n=await this.loadPyoideAndPackages(),{version:s}=t;return s.includes("dev")&&await this.installDevMarimo(n,s),await this.installMarimoAndDeps(n,s),this.installPatches(n),n}async loadPyoideAndPackages(){if(!loadPyodide)throw new Error("loadPyodide is not defined");const t=await loadPyodide({packages:["micropip","docutils","Pygments","jedi","pyodide-http"],indexURL:"https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"});return this.pyodide=t,t}async installDevMarimo(t,n){await t.runPythonAsync(`
      import micropip

      await micropip.install(
        [
          "${x(n)}",
        ],
        deps=False,
        index_urls="https://test.pypi.org/pypi/{package_name}/json"
        );
      `)}async installMarimoAndDeps(t,n){await t.runPythonAsync(`
      import micropip

      await micropip.install(
        [
          "${x(n)}",
          "markdown",
          "pymdown-extensions",
        ],
        deps=False,
        );
      `)}installPatches(t){t.runPython(`
      import pyodide_http
      pyodide_http.patch_urllib()
    `)}async startSession(t){L(this.pyodide,"Pyodide not loaded");const{filename:n,content:s}=await _({pyodide:this.pyodide,...t});return self.messenger={callback:t.onMessage},self.query_params=t.queryParameters,await this.pyodide.loadPackagesFromImports(s,{messageCallback:I.log,errorCallback:I.error}),await this.pyodide.runPythonAsync(`
      print("[py] Starting marimo...")
      import asyncio
      import js
      from marimo._pyodide.pyodide_session import create_session, instantiate

      assert js.messenger, "messenger is not defined"
      assert js.query_params, "query_params is not defined"

      session, bridge = create_session(
        filename="${n}",
        query_params=js.query_params.to_py(),
        message_callback=js.messenger.callback,
      )
      instantiate(session)
      asyncio.create_task(session.start())

      bridge`)}}function x(e){return e?e==="local"?"http://localhost:8000/dist/marimo-0.3.8-py3-none-any.whl":`marimo==${e}`:"marimo >= 0.3.0"}class K{constructor(){g(this,"promise");g(this,"resolve");g(this,"reject");this.promise=new Promise((t,n)=>{this.reject=n,this.resolve=t})}}class X{constructor(t){g(this,"buffer");g(this,"started",!1);g(this,"push",t=>{this.started?this.onMessage(t):this.buffer.push(t)});g(this,"start",()=>{this.started=!0,this.buffer.forEach(t=>this.onMessage(t)),this.buffer=[]});this.onMessage=t,this.buffer=[]}}function A(e){if(!e)return"Unknown error";if(e instanceof Error)return Q(e.message);try{return JSON.stringify(e)}catch{return String(e)}}function Q(e){try{const t=JSON.parse(e);if(!t)return e;if(typeof t=="object"&&"detail"in t&&typeof t.detail=="string")return t.detail}catch{}return e}function me(e){return e}const V=1e10,G=1e3;function F(e,t){const n=e.map(s=>`"${s}"`).join(", ");return new Error(`This RPC instance cannot ${t} because the transport did not provide one or more of these methods: ${n}`)}function Y(e={}){let t={};function n(r){t=r}let s={};function l(r){var o;s.unregisterHandler&&s.unregisterHandler(),s=r,(o=s.registerHandler)==null||o.call(s,fe)}let a;function h(r){if(typeof r=="function"){a=r;return}a=(o,c)=>{const i=r[o];if(i)return i(c);const d=r._;if(!d)throw new Error(`The requested method has no handler: ${o}`);return d(o,c)}}const{maxRequestTime:m=G}=e;e.transport&&l(e.transport),e.requestHandler&&h(e.requestHandler),e._debugHooks&&n(e._debugHooks);let u=0;function w(){return u<=V?++u:u=0}const k=new Map,E=new Map;function R(r,...o){const c=o[0];return new Promise((i,d)=>{var S;if(!s.send)throw F(["send"],"make requests");const p=w(),M={type:"request",id:p,method:r,params:c};k.set(p,{resolve:i,reject:d}),m!==1/0&&E.set(p,setTimeout(()=>{E.delete(p),d(new Error("RPC request timed out."))},m)),(S=t.onSend)==null||S.call(t,M),s.send(M)})}const N=new Proxy(R,{get:(r,o,c)=>o in r?Reflect.get(r,o,c):i=>R(o,i)}),B=N;function O(r,...o){var d;const c=o[0];if(!s.send)throw F(["send"],"send messages");const i={type:"message",id:r,payload:c};(d=t.onSend)==null||d.call(t,i),s.send(i)}const U=new Proxy(O,{get:(r,o,c)=>o in r?Reflect.get(r,o,c):i=>O(o,i)}),z=U,q=new Map,v=new Set;function le(r,o){var c;if(!s.registerHandler)throw F(["registerHandler"],"register message listeners");if(r==="*"){v.add(o);return}q.has(r)||q.set(r,new Set),(c=q.get(r))==null||c.add(o)}function ue(r,o){var c,i;if(r==="*"){v.delete(o);return}(c=q.get(r))==null||c.delete(o),((i=q.get(r))==null?void 0:i.size)===0&&q.delete(r)}async function fe(r){var o,c;if((o=t.onReceive)==null||o.call(t,r),!("type"in r))throw new Error("Message does not contain a type.");if(r.type==="request"){if(!s.send||!a)throw F(["send","requestHandler"],"handle requests");const{id:i,method:d,params:p}=r;let M;try{M={type:"response",id:i,success:!0,payload:await a(d,p)}}catch(S){if(!(S instanceof Error))throw S;M={type:"response",id:i,success:!1,error:S.message}}(c=t.onSend)==null||c.call(t,M),s.send(M);return}if(r.type==="response"){const i=E.get(r.id);i!=null&&clearTimeout(i);const{resolve:d,reject:p}=k.get(r.id)??{};r.success?d==null||d(r.payload):p==null||p(new Error(r.error));return}if(r.type==="message"){for(const d of v)d(r.id,r.payload);const i=q.get(r.id);if(!i)return;for(const d of i)d(r.payload);return}throw new Error(`Unexpected RPC message type: ${r.type}`)}return{setTransport:l,setRequestHandler:h,request:N,requestProxy:B,send:U,sendProxy:z,addMessageListener:le,removeMessageListener:ue,proxy:{send:z,request:B},_setDebugHooks:n}}function Z(e){return Y(e)}const D="[transport-id]";function ee(e,t){const{transportId:n}=t;return n!=null?{[D]:n,data:e}:e}function te(e,t){const{transportId:n,filter:s}=t,l=s==null?void 0:s();if(n!=null&&l!=null)throw new Error("Cannot use both `transportId` and `filter` at the same time");let a=e;if(n){if(e[D]!==n)return[!0];a=e.data}return l===!1?[!0]:[!1,a]}function re(e,t={}){const{transportId:n,filter:s,remotePort:l}=t,a=e,h=l??e;let m;return{send(u){h.postMessage(ee(u,{transportId:n}))},registerHandler(u){m=w=>{const k=w.data,[E,R]=te(k,{transportId:n,filter:()=>s==null?void 0:s(w)});E||u(R)},a.addEventListener("message",m)},unregisterHandler(){m&&a.removeEventListener("message",m)}}}function ne(e){return re(self,e)}const se="marimo-transport";async function oe(){await import("https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js");try{const e=de(),t=await ie(e);self.controller=t,self.pyodide=await t.bootstrap({version:e})}catch(e){console.error("Error bootstrapping",e),P.send.initializedError({error:A(e)})}}async function ie(e){try{return await import(`/wasm/controller.js?version=${e}`)}catch{return new W}}const b=oe(),H=new X(e=>{P.send.kernelMessage({message:e})}),j=new K;let $=!1;const ae={startSession:async e=>{if(await b,$){I.warn("Session already started");return}$=!0;try{L(self.controller,"Controller not loaded");const t=await self.controller.startSession({...e,onMessage:H.push});j.resolve(t),P.send.initialized({})}catch(t){P.send.initializedError({error:A(t)})}},loadPackages:async e=>{await b,await self.pyodide.loadPackagesFromImports(e,{messageCallback:console.log,errorCallback:console.error})},readFile:async e=>(await b,self.pyodide.FS.readFile(e,{encoding:"utf8"})),setInterruptBuffer:async e=>{await b,self.pyodide.setInterruptBuffer(e)},bridge:async e=>{await b;const{functionName:t,payload:n}=e;t==="format"&&await self.pyodide.runPythonAsync(`
        import micropip

        try:
          import black
        except ModuleNotFoundError:
          await micropip.install("black")
        `);const s=await j.promise,l=n==null?null:typeof n=="string"?n:JSON.stringify(n),a=l==null?await s[t]():await s[t](l);return ce.has(t)&&C(self.pyodide,!1),typeof a=="string"?JSON.parse(a):a}},P=Z({transport:ne({transportId:se}),requestHandler:ae});self.rpc=P,P.send("ready",{}),P.addMessageListener("consumerReady",async()=>{await b,H.start()});const ce=new Set(["save","save_app_config","rename_file","create_file_or_directory","delete_file_or_directory","move_file_or_directory","update_file"]);function de(){return self.name}})();
