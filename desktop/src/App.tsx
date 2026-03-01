import { useState, useEffect, useRef, useCallback, MouseEvent as RME } from "react";
import "./styles.css";

const API = "http://127.0.0.1:9876";

interface Keyframe { id:string; time:number; value:number; easing:string; }
interface Envelope { param_name:string; default_value:number; keyframes:Keyframe[]; }
interface Effect { id:string; name:string; effect_type:string; enabled:boolean; envelopes:Record<string,Envelope>; }
interface Clip {
  id:string; source_path:string; start_time:number; end_time:number;
  source_in:number; source_out:number; label:string; enabled:boolean; locked:boolean;
  position_x:number; position_y:number; scale:number; rotation:number;
  opacity:number; volume:number; effects:Effect[]; metadata:Record<string,any>;
}
interface Track {
  id:string; name:string; track_type:string; index:number;
  clips:Clip[]; muted:boolean; solo:boolean; locked:boolean;
  visible:boolean; volume:number; height:number;
}
interface TL {
  id:string; name:string; fps:number; output_width:number; output_height:number;
  aspect_ratio:string; duration:number; settings:any; tracks:Track[];
}

const CLIENTS = [
  { key:"padrinho_podcast", name:"O Padrinho Podcast" },
  { key:"sucessora", name:"A Sucessora" },
  { key:"djalma", name:"Djalma" },
];
const FONTS = ["Arial","Montserrat","Poppins","Roboto","Impact","Oswald","Bebas Neue","Inter","Open Sans","Lato","Raleway","Nunito","Ubuntu"];
const FORMATS = ["9:16","16:9","1:1","4:5","4:3"];
const EASINGS = ["linear","ease_in","ease_out","ease_in_out","ease_in_cubic","ease_out_cubic","ease_in_out_cubic","bezier"];

const TM:Record<string,{icon:string;color:string;type:string;wave?:boolean}> = {
  "C1 - Legenda":  {icon:"C1",color:"#e67e22",type:"sub"},
  "V3 - Overlay":  {icon:"V3",color:"#9b59b6",type:"vid"},
  "V2 - Efeitos":  {icon:"V2",color:"#8e44ad",type:"vid"},
  "V1 - Vídeo":    {icon:"V1",color:"#2196F3",type:"vid"},
  "A1 - Áudio":    {icon:"A1",color:"#2196F3",type:"aud",wave:true},
  "A2 - Áudio 2":  {icon:"A2",color:"#4CAF50",type:"aud",wave:true},
  "A3 - Música":   {icon:"A3",color:"#4CAF50",type:"aud",wave:true},
};

const fmt = (s:number) => {
  const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60),f=Math.floor((s%1)*30);
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}:${String(f).padStart(2,"0")}`;
};
const fmtS = (s:number) => `${Math.floor(s/60)}:${String(Math.floor(s%60)).padStart(2,"0")}`;
const post = async (path:string, body?:any) => {
  const o:RequestInit = body ? {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)} : {};
  return (await fetch(`${API}${path}`,o)).json();
};

function Wave({w,c}:{w:number;c:string}) {
  const pts:string[]=[];const h=26,mid=h/2,step=2;
  for(let x=0;x<w;x+=step){const a=(Math.sin(x*.08)*.3+Math.sin(x*.2)*.4+Math.random()*.3)*mid*.8;pts.push(`${x},${mid-a}`);}
  for(let x=w;x>=0;x-=step){const a=(Math.sin(x*.08)*.3+Math.sin(x*.2)*.4+Math.random()*.3)*mid*.8;pts.push(`${x},${mid+a}`);}
  return <svg width={w} height={h} style={{position:"absolute",top:0,left:0,opacity:.5}}><polygon points={pts.join(" ")} fill={c}/></svg>;
}

export default function App() {
  const [client,setClient]=useState(CLIENTS[0].key);
  const [status,setStatus]=useState("idle");
  const [progress,setProgress]=useState(0);
  const [leftTab,setLeftTab]=useState("media");
  const [rightTab,setRightTab]=useState("props");
  const [tl,setTl]=useState<TL|null>(null);
  const [zoom,setZoom]=useState(1.5);
  const [playhead,setPlayhead]=useState(0);
  const [isPlaying,setIsPlaying]=useState(false);
  const [history,setHistory]=useState<string[]>([]);
  const [selClipId,setSelClipId]=useState<string|null>(null);
  const videoRef=useRef<HTMLVideoElement>(null);
  const [previewSrc,setPreviewSrc]=useState("");
  const [version,setVersion]=useState("0.2.0");
  const [outputFmt,setOutputFmt]=useState("9:16");
  const [dragInfo,setDragInfo]=useState<{id:string;mode:"move"|"trim-l"|"trim-r";sx:number;origS:number;origE:number}|null>(null);
  const tlScrollRef=useRef<HTMLDivElement>(null);
  const [inputVideo,setInputVideo]=useState("");
  const [decupagem,setDecupagem]=useState("");
  const [musicPath,setMusicPath]=useState("");
  const [overlayPath,setOverlayPath]=useState("layoutcorte.png");
  const [learnFolder,setLearnFolder]=useState("");
  const [subFont,setSubFont]=useState("Arial");
  const [subSize,setSubSize]=useState(48);
  const [subColor,setSubColor]=useState("#ffffff");
  const [subOutline,setSubOutline]=useState("#000000");
  const [subOutlineW,setSubOutlineW]=useState(3);
  const [subShadow,setSubShadow]=useState(2);
  const [subShadowC,setSubShadowC]=useState("#000000");
  const [subUpper,setSubUpper]=useState(false);
  const [subBold,setSubBold]=useState(true);
  const [subItalic,setSubItalic]=useState(false);
  const [subPos,setSubPos]=useState(2);
  const [subMarginV,setSubMarginV]=useState(180);
  const [subMarginL,setSubMarginL]=useState(40);
  const [subMarginR,setSubMarginR]=useState(40);
  const [subBgC,setSubBgC]=useState("#000000");
  const [subBgOp,setSubBgOp]=useState(0);
  const [subHL,setSubHL]=useState("");
  const [subSpacing,setSubSpacing]=useState(0);
  const [subMaxC,setSubMaxC]=useState(35);
  const [subBorder,setSubBorder]=useState(1);
  const [silAggr,setSilAggr]=useState(12);
  const [zoomI,setZoomI]=useState(1.12);
  const [dynReframe,setDynReframe]=useState(true);
  const [skipSil,setSkipSil]=useState(false);
  const [skipOv,setSkipOv]=useState(false);
  const [skipSub,setSkipSub]=useState(false);
  const [kfParam,setKfParam]=useState("scale");
  const [kfTime,setKfTime]=useState(0);
  const [kfValue,setKfValue]=useState(1.0);
  const [kfEasing,setKfEasing]=useState("ease_in_out_cubic");
  const [updateInfo,setUpdateInfo]=useState<any>(null);

  const addH=useCallback((msg:string)=>{setHistory(h=>[`${new Date().toLocaleTimeString()} — ${msg}`,...h].slice(0,80));},[]);

  useEffect(()=>{
    const iv=setInterval(async()=>{
      try{const s=await post("/api/status");setStatus(s.status||"idle");setProgress(s.progress||0);if(s.version)setVersion(s.version);if(s.status==="done"&&!tl)loadProject();}catch{}
    },1500);
    return ()=>clearInterval(iv);
  },[tl]);

  const loadProject=async()=>{try{const p=await post("/api/project");if(p&&!p.error&&p.tracks){setTl(p);setOutputFmt(p.aspect_ratio||"9:16");addH(`Projeto: ${p.tracks?.length} tracks`);}}catch{}};

  useEffect(()=>{
    post("/api/presets").then((pr:any)=>{const p=pr[client];if(!p)return;setSubFont(p.subtitle_font||"Arial");setSubSize(p.subtitle_font_size||48);setSubColor(p.subtitle_color||"#ffffff");setZoomI(p.zoom_intensity||1.12);setSilAggr(p.silence_aggressiveness||12);}).catch(()=>{});
  },[client]);

  const pps=60*zoom;
  const totalDur=tl?Math.max(tl.duration,10):60;
  const tlW=totalDur*pps+200;

  const getSel=():({track:Track,clip:Clip}|null)=>{
    if(!tl||!selClipId)return null;
    for(const t of tl.tracks)for(const c of t.clips)if(c.id===selClipId)return{track:t,clip:c};return null;
  };

  const playClipF=(c:Clip)=>{if(c.source_path){setPreviewSrc(`${API}/api/file/${c.source_path}`);addH(`Preview: ${c.label}`);}};

  // Timeline API calls
  const tlApi=async(ep:string,body:any)=>{await post(`/api/timeline/${ep}`,body);await loadProject();};
  const tlMove=async(id:string,s:number)=>{await tlApi("move-clip",{clip_id:id,new_start:Math.max(0,s)});};
  const tlTrim=async(id:string,s?:number,e?:number)=>{await tlApi("trim-clip",{clip_id:id,new_start:s,new_end:e});};
  const tlSplit=async(id:string,t:number)=>{await tlApi("split-clip",{clip_id:id,time:t});addH(`Split @ ${t.toFixed(2)}s`);};
  const tlDel=async(id:string)=>{await tlApi("delete-clip",{clip_id:id});setSelClipId(null);addH("Clip deletado");};
  const tlCProp=async(id:string,p:any)=>{await tlApi("clip-props",{clip_id:id,...p});};
  const tlTProp=async(n:string,p:any)=>{await tlApi("track-props",{track_name:n,...p});};
  const tlAddKf=async(id:string,param:string,time:number,value:number,easing:string)=>{await tlApi("add-keyframe",{clip_id:id,param,time,value,easing});addH(`KF+ ${param}=${value.toFixed(2)}`);};
  const tlDelKf=async(id:string,param:string,kid:string)=>{await tlApi("delete-keyframe",{clip_id:id,param,keyframe_id:kid});addH("KF-");};
  const tlFmt=async(f:string)=>{await post("/api/timeline/set-format",{preset:f});setOutputFmt(f);await loadProject();addH(`Formato: ${f}`);};

  // Drag/Trim handlers
  const onClipDown=(e:RME,clip:Clip,track:Track,mode:"move"|"trim-l"|"trim-r")=>{
    if(track.locked||clip.locked)return;e.stopPropagation();e.preventDefault();
    setSelClipId(clip.id);setDragInfo({id:clip.id,mode,sx:e.clientX,origS:clip.start_time,origE:clip.end_time});
  };

  useEffect(()=>{
    if(!dragInfo)return;
    const onMove=(e:globalThis.MouseEvent)=>{
      const dx=(e.clientX-dragInfo.sx)/pps;
      if(dragInfo.mode==="trim-l")tlTrim(dragInfo.id,Math.max(0,dragInfo.origS+dx),undefined);
      else if(dragInfo.mode==="trim-r")tlTrim(dragInfo.id,undefined,Math.max(dragInfo.origS+0.1,dragInfo.origE+dx));
      else tlMove(dragInfo.id,Math.max(0,dragInfo.origS+dx));
    };
    const onUp=()=>setDragInfo(null);
    window.addEventListener("mousemove",onMove);window.addEventListener("mouseup",onUp);
    return ()=>{window.removeEventListener("mousemove",onMove);window.removeEventListener("mouseup",onUp);};
  },[dragInfo]);

  const onRulerClick=(e:RME)=>{
    const rect=(e.currentTarget as HTMLElement).getBoundingClientRect();
    const x=e.clientX-rect.left+(tlScrollRef.current?.scrollLeft||0);
    setPlayhead(x/pps);if(videoRef.current)videoRef.current.currentTime=x/pps;
  };

  const handleProcess=async(po:boolean)=>{
    if(!inputVideo)return alert("Selecione vídeo.");addH(po?"Preview...":"Pipeline...");setTl(null);
    await post(po?"/api/process-preview":"/api/process",{input_video:inputVideo,client,decupagem:decupagem||undefined,music:musicPath||undefined,overlay_path:overlayPath||undefined,dynamic_reframe:dynReframe,skip_silence:skipSil,skip_overlay:skipOv,skip_subtitles:skipSub});
  };
  const handleExport=async()=>{if(!tl)return;addH("Exportando...");await post("/api/export",{output_dir:"output/export",music:musicPath||undefined});};
  const handleLearn=async()=>{if(!learnFolder)return;addH(`Learn: ${learnFolder}`);await post("/api/learn-folder",{folder_path:learnFolder,client_name:client});};
  const handleSavePreset=async()=>{
    await post("/api/save-preset",{key:client,preset:{subtitle_font:subFont,subtitle_font_size:subSize,subtitle_color:subColor,subtitle_outline_color:subOutline,subtitle_outline_width:subOutlineW,subtitle_shadow_depth:subShadow,subtitle_bold:subBold,subtitle_italic:subItalic,subtitle_uppercase:subUpper,subtitle_alignment:subPos,subtitle_margin_bottom:subMarginV,subtitle_margin_left:subMarginL,subtitle_margin_right:subMarginR,subtitle_bg_color:subBgC,subtitle_bg_opacity:subBgOp,subtitle_highlight_color:subHL||undefined,subtitle_spacing:subSpacing,subtitle_max_chars:subMaxC,subtitle_border_style:subBorder,zoom_intensity:zoomI,silence_aggressiveness:silAggr}});addH(`Preset: ${client}`);
  };

  // Keyboard
  useEffect(()=>{
    const h=(e:KeyboardEvent)=>{
      if(e.key==="Delete"&&selClipId){e.preventDefault();tlDel(selClipId);}
      if(e.key===" "){e.preventDefault();if(videoRef.current){isPlaying?videoRef.current.pause():videoRef.current.play();setIsPlaying(!isPlaying);}}
      if(e.key==="b"&&selClipId){e.preventDefault();tlSplit(selClipId,playhead);}
    };
    window.addEventListener("keydown",h);return ()=>window.removeEventListener("keydown",h);
  },[selClipId,playhead,isPlaying]);

  const sel=getSel();

  return (
    <div className="app">
      {/* TOPBAR */}
      <div className="topbar">
        <span className="logo">VCLIP</span>
        <div className="client-tabs">{CLIENTS.map(c=><button key={c.key} className={`ctab ${client===c.key?"active":""}`} onClick={()=>setClient(c.key)}>📋 {c.name}</button>)}</div>
        <div className="fmt-sel">{FORMATS.map(f=><button key={f} className={`fmtbtn ${outputFmt===f?"active":""}`} onClick={()=>tlFmt(f)}>{f}</button>)}</div>
        <div className="topbar-r">
          {status==="processing"&&<div className="prog"><div className="fill" style={{width:`${progress}%`}}/></div>}
          <span className={`badge ${status}`}>{status.toUpperCase()}</span>
          <span className="ver">v{version}</span>
        </div>
      </div>

      <div className="main">
        {/* LEFT */}
        <div className="left">
          <div className="tabs">{[{k:"media",l:"Media"},{k:"edit",l:"Legendas"},{k:"ai",l:"IA"},{k:"learn",l:"Learn"},{k:"update",l:"⬆"}].map(t=><button key={t.k} className={`tab ${leftTab===t.k?"active":""}`} onClick={()=>setLeftTab(t.k)}>{t.l}</button>)}</div>
          <div className="pcontent">
            {leftTab==="media"&&<>
              <Sec t="Entrada">
                <FF l="Vídeo"><input className="fi" value={inputVideo} onChange={e=>setInputVideo(e.target.value)} placeholder="video.mp4"/></FF>
                <FF l="Decupagem"><input className="fi" value={decupagem} onChange={e=>setDecupagem(e.target.value)} placeholder="cortes.txt"/></FF>
                <FF l="Música"><input className="fi" value={musicPath} onChange={e=>setMusicPath(e.target.value)} placeholder="musica.mp3"/></FF>
                <FF l="Overlay"><input className="fi" value={overlayPath} onChange={e=>setOverlayPath(e.target.value)} placeholder="layoutcorte.png"/></FF>
              </Sec>
              {tl&&<Sec t={`Clips V1`}>{tl.tracks.find(t=>t.name==="V1 - Vídeo")?.clips.map((c,i)=>(
                <div key={c.id} className={`mitem ${selClipId===c.id?"sel":""}`} onClick={()=>{setSelClipId(c.id);playClipF(c);}}><span className="micon">🎬</span><span className="mname">{c.label||`Clip ${i+1}`}</span><span className="mdur">{(c.end_time-c.start_time).toFixed(1)}s</span></div>
              ))}</Sec>}
            </>}
            {leftTab==="edit"&&<>
              <Sec t="Fonte"><FF l="Fonte"><select className="fi" value={subFont} onChange={e=>setSubFont(e.target.value)}>{FONTS.map(f=><option key={f}>{f}</option>)}</select></FF><div className="fr"><FF l="Tam"><input className="fi" type="number" value={subSize} onChange={e=>setSubSize(+e.target.value)}/></FF><FF l="Esp"><input className="fi" type="number" value={subSpacing} onChange={e=>setSubSpacing(+e.target.value)}/></FF></div><div className="fr"><label className="ck"><input type="checkbox" checked={subBold} onChange={e=>setSubBold(e.target.checked)}/>B</label><label className="ck"><input type="checkbox" checked={subItalic} onChange={e=>setSubItalic(e.target.checked)}/>I</label><label className="ck"><input type="checkbox" checked={subUpper} onChange={e=>setSubUpper(e.target.checked)}/>AA</label></div></Sec>
              <Sec t="Cores"><div className="fr"><FF l="Txt"><input type="color" className="fic" value={subColor} onChange={e=>setSubColor(e.target.value)}/></FF><FF l="Out"><input type="color" className="fic" value={subOutline} onChange={e=>setSubOutline(e.target.value)}/></FF><FF l="Shd"><input type="color" className="fic" value={subShadowC} onChange={e=>setSubShadowC(e.target.value)}/></FF></div><div className="fr"><FF l="Out W"><input className="fi" type="number" value={subOutlineW} onChange={e=>setSubOutlineW(+e.target.value)}/></FF><FF l="Shd D"><input className="fi" type="number" value={subShadow} onChange={e=>setSubShadow(+e.target.value)}/></FF></div><FF l="HL"><div className="fr"><input type="color" className="fic" value={subHL||"#ffff00"} onChange={e=>setSubHL(e.target.value)}/><label className="ck"><input type="checkbox" checked={!!subHL} onChange={e=>setSubHL(e.target.checked?"#ffff00":"")}/>On</label></div></FF></Sec>
              <Sec t="BG"><div className="fr"><FF l="Cor"><input type="color" className="fic" value={subBgC} onChange={e=>setSubBgC(e.target.value)}/></FF><FF l={`Op ${subBgOp}`}><input type="range" min={0} max={255} value={subBgOp} onChange={e=>setSubBgOp(+e.target.value)} style={{width:"100%"}}/></FF></div><FF l="Borda"><select className="fi" value={subBorder} onChange={e=>setSubBorder(+e.target.value)}><option value={1}>Outline</option><option value={3}>Box</option><option value={4}>Out+Box</option></select></FF></Sec>
              <Sec t="Pos"><FF l="Align"><select className="fi" value={subPos} onChange={e=>setSubPos(+e.target.value)}><option value={2}>Inf Centro</option><option value={1}>Inf Esq</option><option value={3}>Inf Dir</option><option value={6}>Top Centro</option><option value={5}>Top Esq</option><option value={7}>Top Dir</option><option value={8}>Centro</option></select></FF><div className="fr"><FF l="MV"><input className="fi" type="number" value={subMarginV} onChange={e=>setSubMarginV(+e.target.value)}/></FF><FF l="ML"><input className="fi" type="number" value={subMarginL} onChange={e=>setSubMarginL(+e.target.value)}/></FF><FF l="MR"><input className="fi" type="number" value={subMarginR} onChange={e=>setSubMarginR(+e.target.value)}/></FF></div><FF l={`Max ${subMaxC}ch`}><input type="range" min={15} max={60} value={subMaxC} onChange={e=>setSubMaxC(+e.target.value)} style={{width:"100%"}}/></FF></Sec>
              <Sec t="Preview"><div className="subprev"><span style={{fontFamily:subFont,fontSize:Math.min(subSize*.35,22),color:subColor,fontWeight:subBold?700:400,fontStyle:subItalic?"italic":"normal",textTransform:subUpper?"uppercase":"none",WebkitTextStroke:`${Math.max(subOutlineW*.2,.5)}px ${subOutline}`,textShadow:`${subShadow}px ${subShadow}px 2px ${subShadowC}`,letterSpacing:subSpacing,background:subBgOp>0?subBgC+Math.round(subBgOp*100/255).toString(16).padStart(2,"0"):"transparent",padding:subBgOp>0?"4px 8px":"0",borderRadius:3}}>O mercado financeiro</span></div></Sec>
              <button className="btn accent full" onClick={handleSavePreset}>💾 Salvar Preset</button>
            </>}
            {leftTab==="ai"&&<><Sec t="Silêncio"><FF l={`Aggr: ${silAggr}dB`}><input type="range" min={6} max={20} value={silAggr} onChange={e=>setSilAggr(+e.target.value)} style={{width:"100%"}}/></FF><label className="ck"><input type="checkbox" checked={skipSil} onChange={e=>setSkipSil(e.target.checked)}/>Skip</label></Sec><Sec t="Zoom"><FF l={`${zoomI.toFixed(2)}x`}><input type="range" min={1} max={1.3} step={.01} value={zoomI} onChange={e=>setZoomI(+e.target.value)} style={{width:"100%"}}/></FF><label className="ck"><input type="checkbox" checked={dynReframe} onChange={e=>setDynReframe(e.target.checked)}/>Anchor rosto</label></Sec><Sec t="Skip"><label className="ck"><input type="checkbox" checked={skipOv} onChange={e=>setSkipOv(e.target.checked)}/>Overlay</label><label className="ck"><input type="checkbox" checked={skipSub} onChange={e=>setSkipSub(e.target.checked)}/>Legendas</label></Sec></>}
            {leftTab==="learn"&&<Sec t="Learn"><FF l="Pasta"><input className="fi" value={learnFolder} onChange={e=>setLearnFolder(e.target.value)}/></FF><button className="btn accent full" onClick={handleLearn}>🧠 Aprender</button></Sec>}
            {leftTab==="update"&&<Sec t="Update"><div className="ucard"><div className="ut">v{version}</div></div><button className="btn sec full" onClick={async()=>{const i=await post("/api/update-check",{});setUpdateInfo(i);}}>🔍 Check</button>{updateInfo?.has_update&&<button className="btn suc full" style={{marginTop:6}} onClick={async()=>{await post("/api/update-apply",{});setUpdateInfo(null);}}>⬇ Update</button>}<button className="btn sec full sm" style={{marginTop:6}} onClick={()=>post("/api/update-rollback",{})}>↩ Rollback</button></Sec>}
          </div>
        </div>

        {/* CENTER */}
        <div className="center">
          <div className="preview">
            {previewSrc?<video ref={videoRef} src={previewSrc} onTimeUpdate={()=>{if(videoRef.current)setPlayhead(videoRef.current.currentTime)}} onEnded={()=>setIsPlaying(false)} onPlay={()=>setIsPlaying(true)} onPause={()=>setIsPlaying(false)} style={{maxHeight:"100%",maxWidth:"100%",borderRadius:6}}/>:
            <div className="phold"><div className="phi">🎞️</div><div className="pht">Processe um vídeo</div><div className="phh">{outputFmt} • {tl?`${tl.output_width}×${tl.output_height}`:"1080×1920"}</div></div>}
          </div>
          <div className="transport">
            <span className="tc">{fmt(playhead)}</span>
            <div className="tbtns">
              <button className="tb" onClick={()=>{if(videoRef.current)videoRef.current.currentTime-=1/30}}>◀</button>
              <button className="tb play" onClick={()=>{if(!videoRef.current)return;isPlaying?videoRef.current.pause():videoRef.current.play();setIsPlaying(!isPlaying)}}>{isPlaying?"⏸":"▶"}</button>
              <button className="tb" onClick={()=>{if(videoRef.current)videoRef.current.currentTime+=1/30}}>▶</button>
            </div>
            {selClipId&&<div className="tl-tools"><button className="btn sec sm" onClick={()=>tlSplit(selClipId,playhead)}>✂ Split</button><button className="btn err-btn sm" onClick={()=>tlDel(selClipId)}>🗑</button></div>}
            <div className="abtns">
              <button className="btn sec sm" onClick={()=>handleProcess(true)} disabled={status==="processing"}>Preview</button>
              <button className="btn accent sm" onClick={()=>handleProcess(false)} disabled={status==="processing"}>{status==="processing"?`${progress}%...`:"⚡ IA"}</button>
              <button className="btn suc sm" onClick={handleExport} disabled={!tl}>📦 Export</button>
            </div>
          </div>
          {/* TIMELINE */}
          <div className="tlc">
            <div className="tltbar"><span className="tll">Timeline</span><input type="range" className="tlz" min={.3} max={5} step={.1} value={zoom} onChange={e=>setZoom(+e.target.value)}/><span className="tlzv">{zoom.toFixed(1)}x</span><span className="tlinfo">{tl?`${tl.tracks.reduce((a,t)=>a+t.clips.length,0)} clips • ${totalDur.toFixed(1)}s`:""}</span><span className="tlfmt">{outputFmt}</span></div>
            <div className="tlbody">
              <div className="tlheaders">
                <div className="tlrs"/>
                {tl?.tracks.map(track=>{const m=TM[track.name]||{icon:"?",color:"#666",type:"vid"};return(
                  <div key={track.id} className={`tlh ${m.type}`}>
                    <span className="tlock" onClick={()=>tlTProp(track.name,{locked:!track.locked})}>{track.locked?"🔒":"🔓"}</span>
                    <span className="tbdg" style={{background:m.color}}>{m.icon}</span>
                    <span className="tnm">{track.name.split(" - ")[1]||track.name}</span>
                    <div className="tctrl">
                      <span className={`tc2 ${track.muted?"on":""}`} onClick={()=>tlTProp(track.name,{muted:!track.muted})}>M</span>
                      <span className={`tc2 ${track.solo?"on":""}`} onClick={()=>tlTProp(track.name,{solo:!track.solo})}>S</span>
                    </div>
                  </div>
                )})}
              </div>
              <div className="tlscroll" ref={tlScrollRef}>
                <div style={{width:tlW,position:"relative"}}>
                  <div className="tlruler" onClick={onRulerClick}>{Array.from({length:Math.ceil(totalDur)+1},(_,i)=>{const maj=i%5===0;return <div key={i} className={`tlmk ${maj?"maj":""}`} style={{left:i*pps}}>{maj&&<span className="tltime">{fmtS(i)}</span>}</div>})}</div>
                  <div className="tllanes">
                    {tl?.tracks.map(track=>{const m=TM[track.name]||{icon:"?",color:"#666",type:"vid",wave:false};return(
                      <div key={track.id} className={`tllane ${m.type} ${track.muted?"muted":""}`}>
                        {track.clips.map(cl=>{const l=cl.start_time*pps,w=Math.max((cl.end_time-cl.start_time)*pps,8),isSel=selClipId===cl.id;return(
                          <div key={cl.id} className={`tlclip ${m.type} ${isSel?"sel":""} ${cl.locked?"locked":""}`} style={{left:l,width:w,background:m.color}} onClick={e=>{e.stopPropagation();setSelClipId(cl.id);playClipF(cl);}} onMouseDown={e=>onClipDown(e,cl,track,"move")}>
                            <div className="trim-h trim-l" onMouseDown={e=>onClipDown(e,cl,track,"trim-l")}/>
                            <span className="tlcl">{cl.label||"clip"}</span>
                            {m.wave&&w>30&&<Wave w={w} c="rgba(255,255,255,.3)"/>}
                            {cl.effects.flatMap(fx=>Object.values(fx.envelopes).flatMap(env=>env.keyframes.map(kf=><div key={kf.id} className="kf-diamond" style={{left:`${(kf.time/(cl.end_time-cl.start_time))*100}%`}} title={`${env.param_name}=${kf.value.toFixed(2)}`}/>)))}
                            <div className="trim-h trim-r" onMouseDown={e=>onClipDown(e,cl,track,"trim-r")}/>
                          </div>
                        )})}
                      </div>
                    )})}
                    <div className="tlph" style={{left:playhead*pps}}><div className="tlphh"/><div className="tlphl"/></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="right">
          <div className="tabs"><button className={`tab ${rightTab==="props"?"active":""}`} onClick={()=>setRightTab("props")}>Clip</button><button className={`tab ${rightTab==="kf"?"active":""}`} onClick={()=>setRightTab("kf")}>KF</button><button className={`tab ${rightTab==="history"?"active":""}`} onClick={()=>setRightTab("history")}>Log</button></div>
          <div className="pcontent">
            {rightTab==="props"&&<>
              <Sec t="Projeto">{tl?<><PR l="Tracks" v={tl.tracks.length}/><PR l="Dur" v={`${totalDur.toFixed(1)}s`}/><PR l="Out" v={`${tl.output_width}×${tl.output_height}`}/><PR l="FPS" v={tl.fps}/><PR l="Fmt" v={tl.aspect_ratio}/></>:<p className="hint">—</p>}</Sec>
              {sel&&<>
                <Sec t={sel.clip.label}><PR l="Start" v={sel.clip.start_time.toFixed(3)+"s"}/><PR l="End" v={sel.clip.end_time.toFixed(3)+"s"}/><PR l="Dur" v={(sel.clip.end_time-sel.clip.start_time).toFixed(3)+"s"}/><PR l="Track" v={sel.track.name.split(" - ")[1]}/></Sec>
                <Sec t="Transform">
                  <FF l={`Scale ${sel.clip.scale.toFixed(2)}`}><input type="range" min={0.5} max={2} step={0.01} value={sel.clip.scale} onChange={e=>tlCProp(sel.clip.id,{scale:+e.target.value})} style={{width:"100%"}}/></FF>
                  <FF l={`Pos X ${sel.clip.position_x.toFixed(0)}`}><input type="range" min={-500} max={500} value={sel.clip.position_x} onChange={e=>tlCProp(sel.clip.id,{position_x:+e.target.value})} style={{width:"100%"}}/></FF>
                  <FF l={`Pos Y ${sel.clip.position_y.toFixed(0)}`}><input type="range" min={-500} max={500} value={sel.clip.position_y} onChange={e=>tlCProp(sel.clip.id,{position_y:+e.target.value})} style={{width:"100%"}}/></FF>
                  <FF l={`Opacity ${sel.clip.opacity.toFixed(2)}`}><input type="range" min={0} max={1} step={0.01} value={sel.clip.opacity} onChange={e=>tlCProp(sel.clip.id,{opacity:+e.target.value})} style={{width:"100%"}}/></FF>
                  <FF l={`Volume ${sel.clip.volume.toFixed(2)}`}><input type="range" min={0} max={2} step={0.01} value={sel.clip.volume} onChange={e=>tlCProp(sel.clip.id,{volume:+e.target.value})} style={{width:"100%"}}/></FF>
                  <FF l={`Rot ${sel.clip.rotation}°`}><input type="range" min={-180} max={180} value={sel.clip.rotation} onChange={e=>tlCProp(sel.clip.id,{rotation:+e.target.value})} style={{width:"100%"}}/></FF>
                </Sec>
                <Sec t="Ações"><div className="fr"><button className="btn sec sm full" onClick={()=>tlSplit(sel.clip.id,playhead)}>✂ Split</button><button className="btn err-btn sm full" onClick={()=>tlDel(sel.clip.id)}>🗑 Del</button></div><label className="ck"><input type="checkbox" checked={sel.clip.locked} onChange={e=>tlCProp(sel.clip.id,{locked:e.target.checked})}/>🔒 Lock</label></Sec>
              </>}
            </>}
            {rightTab==="kf"&&<>{sel?<>
              <Sec t="Adicionar KF">
                <FF l="Param"><select className="fi" value={kfParam} onChange={e=>setKfParam(e.target.value)}><option value="scale">Scale</option><option value="position_x">Pos X</option><option value="position_y">Pos Y</option><option value="opacity">Opacity</option><option value="zoom">Zoom</option><option value="rotation">Rotation</option></select></FF>
                <div className="fr"><FF l="T (s)"><input className="fi" type="number" step={0.1} value={kfTime} onChange={e=>setKfTime(+e.target.value)}/></FF><FF l="Val"><input className="fi" type="number" step={0.01} value={kfValue} onChange={e=>setKfValue(+e.target.value)}/></FF></div>
                <FF l="Ease"><select className="fi" value={kfEasing} onChange={e=>setKfEasing(e.target.value)}>{EASINGS.map(e=><option key={e} value={e}>{e}</option>)}</select></FF>
                <button className="btn accent full" onClick={()=>tlAddKf(sel.clip.id,kfParam,kfTime,kfValue,kfEasing)}>＋ Add KF</button>
              </Sec>
              {sel.clip.effects.map(fx=><Sec key={fx.id} t={fx.name}>{Object.values(fx.envelopes).map(env=><div key={env.param_name} className="kf-env"><div className="kf-env-name">{env.param_name} ({env.keyframes.length})</div>{env.keyframes.map(kf=><div key={kf.id} className="kf-item"><span className="kf-diamond-sm"/><span className="kf-info">{kf.time.toFixed(2)}s = {kf.value.toFixed(3)}</span><span className="kf-ease">{kf.easing.replace("ease_","")}</span><button className="kf-del" onClick={()=>tlDelKf(sel.clip.id,env.param_name,kf.id)}>✕</button></div>)}</div>)}</Sec>)}
              {!sel.clip.effects.length&&<p className="hint">Sem keyframes</p>}
            </>:<p className="hint">Selecione clip</p>}</>}
            {rightTab==="history"&&<Sec t="Log">{history.length?history.map((h,i)=><div key={i} className="hitem">{h}</div>):<p className="hint">—</p>}</Sec>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Sec({t,children}:{t:string;children:React.ReactNode}){return<div className="sec"><div className="stitle">{t}</div>{children}</div>}
function FF({l,children}:{l:string;children:React.ReactNode}){return<div className="ff"><label className="ffl">{l}</label>{children}</div>}
function PR({l,v}:{l:string;v:any}){return<div className="pr"><span className="prl">{l}</span><span className="prv">{String(v)}</span></div>}
