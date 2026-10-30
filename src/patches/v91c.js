
/* ---------- phones & small screens: menu sidebar becomes a top tab strip; the character screen stacks (character on top, panels in a scrolling sheet) ---------- */
(function(){const st=document.createElement('style');st.textContent=`.inmenu #ab89{display:none!important}
@media (max-width:820px),(max-height:500px){
 .inmenu #edfloat{display:none!important}
 #menu .shell{flex-direction:column!important}
 #menu .nav{width:auto!important;flex-direction:row!important;align-items:center;gap:4px!important;padding:calc(6px + env(safe-area-inset-top,0px)) 8px 6px!important;overflow-x:auto;overflow-y:hidden;flex:none!important;border-right:0!important;border-bottom:1px solid var(--ln87,rgba(255,255,255,.15));box-shadow:none!important;-webkit-overflow-scrolling:touch;scrollbar-width:none}
 #menu .nav::-webkit-scrollbar{display:none}
 #menu .nav .logo,#menu .nav .ver{display:none!important}
 #menu .nav .ni{flex:none;padding:9px 11px!important;font-size:11px!important;letter-spacing:.12em!important;white-space:nowrap;clip-path:none!important;gap:6px}
 #menu .nav .ni i{width:16px!important;height:16px!important}#menu .nav .ni i svg{width:14px!important;height:14px!important}
 #menu .nav .ni.on{box-shadow:inset 0 -2px var(--gold87,#e3c26c)!important}
 #menu .nav .mb{flex:none;margin:0 4px 0 0!important;padding:9px 14px!important;font-size:12px!important;white-space:nowrap;display:inline-block}
 #menu .content{padding:14px 14px calc(14px + env(safe-area-inset-bottom,0px))!important;max-width:none!important;margin:0!important;flex:1;min-height:0;width:auto!important}
 #menu .content h2{font-size:24px!important}
 #menu .shell.cs89on .content.csw89{padding:0!important;overflow:hidden!important}
 .cs89{display:flex!important;flex-direction:column;height:100%;gap:0!important}
 .csm89{flex:0 0 42%;min-height:0!important}
 .csp89{display:flex!important;flex-direction:column;gap:10px;flex:1;min-height:0;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:10px 10px calc(14px + env(safe-area-inset-bottom,0px));background:linear-gradient(180deg,rgba(5,7,12,.86),rgba(5,7,12,.96));box-shadow:0 -1px 0 rgba(200,220,255,.15)}
 .csl89,.csr89{overflow:visible!important;padding:12px!important}
 .csl89 h2{font-size:22px!important;margin:2px 0 6px!important}.csl89 .dir87k{display:none}
 .csb89{grid-template-columns:repeat(3,1fr)!important;gap:8px!important;padding:10px!important}.st89 em{font-size:17px!important}
 .hint89{font-size:9px!important;bottom:4px!important}
 .hs90{grid-template-columns:96px 1fr 30px!important;margin:10px 0!important}.hs90 input::-webkit-slider-thumb{width:18px!important;height:24px!important}
 .ct90 button{padding:9px 8px!important}.gr90{grid-template-columns:repeat(auto-fill,minmax(70px,1fr))!important}.sws90{grid-template-columns:repeat(auto-fill,minmax(30px,1fr))!important}
 .pk89{grid-template-columns:repeat(auto-fill,minmax(92px,1fr))!important}.ti89{width:52px!important;height:52px!important}
}
@media (max-height:500px) and (orientation:landscape){
 .cs89{flex-direction:row!important}
 .csm89{flex:0 0 40%}
 .csp89{box-shadow:-1px 0 0 rgba(200,220,255,.15)}
}`;document.head.appendChild(st)})();
