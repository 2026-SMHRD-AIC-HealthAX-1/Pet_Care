(() => {
  'use strict';
  const videoInput=document.getElementById('videoInput'),video=document.getElementById('video'),stage=document.getElementById('stage'),layer=document.getElementById('roiLayer'),empty=document.getElementById('emptyState');
  const roiName=document.getElementById('roiName'),roiList=document.getElementById('roiList'),roiCount=document.getElementById('roiCount'),cameraId=document.getElementById('cameraId'),jsonOutput=document.getElementById('jsonOutput'),copyJson=document.getElementById('copyJson'),deleteSelected=document.getElementById('deleteSelected'),validation=document.getElementById('validationMessage');
  let rois=[],selectedId=null,gesture=null,objectUrl=null;
  const names={WATER_BOWL:'물그릇',FOOD_BOWL:'밥그릇',BED:'침대',OTHER:'기타'};
  const clamp=(v,min,max)=>Math.min(max,Math.max(min,v));
  const round=v=>Number(v.toFixed(4));
  function syncVideoRect(){
    if(!video.videoWidth||!video.videoHeight)return;
    const sw=stage.clientWidth,sh=stage.clientHeight,vr=video.videoWidth/video.videoHeight,sr=sw/sh;
    let w,h,left,top;if(sr>vr){h=sh;w=h*vr;left=(sw-w)/2;top=0}else{w=sw;h=w/vr;left=0;top=(sh-h)/2}
    Object.assign(layer.style,{left:left+'px',top:top+'px',width:w+'px',height:h+'px'});render();
  }
  function nextId(){let n=1;const used=new Set(rois.map(r=>r.roi_id));while(used.has(`ROI-${String(n).padStart(3,'0')}`))n++;return `ROI-${String(n).padStart(3,'0')}`}
  function payload(){return {camera_id:(cameraId.value||'CAM-001').trim(),roi_areas:rois.map(r=>({roi_id:r.roi_id,roi_name:r.roi_name,roi_type:'RECTANGLE',x:round(r.x),y:round(r.y),width:round(r.width),height:round(r.height)}))}}
  function valid(r){return r.x>=0&&r.y>=0&&r.width>0&&r.height>0&&r.x+r.width<=1.00001&&r.y+r.height<=1.00001}
  function render(){
    layer.innerHTML='';rois.forEach(r=>{const el=document.createElement('div');el.className='roi-box'+(r.roi_id===selectedId?' selected':'');el.dataset.id=r.roi_id;Object.assign(el.style,{left:(r.x*100)+'%',top:(r.y*100)+'%',width:(r.width*100)+'%',height:(r.height*100)+'%'});el.innerHTML=`<span class="roi-label">${names[r.roi_name]||r.roi_name} · ${r.roi_id}</span><span class="resize-handle" data-resize="1"></span>`;layer.appendChild(el)});
    roiCount.textContent=`${rois.length}개`;deleteSelected.disabled=!selectedId;
    roiList.innerHTML=rois.length?'':`<div class="list-empty">아직 지정한 영역이 없습니다.</div>`;
    rois.forEach(r=>{const item=document.createElement('div');item.className='roi-item'+(r.roi_id===selectedId?' selected':'');item.dataset.id=r.roi_id;item.innerHTML=`<div class="roi-item-top"><span>${names[r.roi_name]||r.roi_name}</span><span>${r.roi_id}</span></div><div class="roi-coords">x ${round(r.x)} · y ${round(r.y)}<br>w ${round(r.width)} · h ${round(r.height)}</div>`;roiList.appendChild(item)});
    jsonOutput.textContent=JSON.stringify(payload(),null,2);
    if(!rois.length){validation.className='validation-message';validation.textContent='ROI를 지정하면 좌표 검증 결과가 표시됩니다.'}else if(rois.every(valid)){validation.className='validation-message ok';validation.textContent='✓ 모든 ROI가 0~1 범위이며 영역 끝점도 1을 넘지 않습니다.'}else{validation.className='validation-message error';validation.textContent='좌표 범위를 확인해주세요.'}
    console.log('[ROI JSON]',payload());
  }
  function point(e){const rect=layer.getBoundingClientRect();return{x:clamp((e.clientX-rect.left)/rect.width,0,1),y:clamp((e.clientY-rect.top)/rect.height,0,1)}}
  layer.addEventListener('pointerdown',e=>{if(!layer.classList.contains('ready'))return;const p=point(e),box=e.target.closest('.roi-box');if(box){selectedId=box.dataset.id;const r=rois.find(x=>x.roi_id===selectedId);gesture={type:e.target.dataset.resize?'resize':'move',start:p,orig:{...r}}}else{const id=nextId();selectedId=id;rois.push({roi_id:id,roi_name:roiName.value,x:p.x,y:p.y,width:0,height:0});gesture={type:'create',start:p,id}}layer.setPointerCapture(e.pointerId);render()});
  layer.addEventListener('pointermove',e=>{if(!gesture)return;const p=point(e),r=rois.find(x=>x.roi_id===selectedId);if(!r)return;if(gesture.type==='create'){r.x=Math.min(gesture.start.x,p.x);r.y=Math.min(gesture.start.y,p.y);r.width=Math.abs(p.x-gesture.start.x);r.height=Math.abs(p.y-gesture.start.y)}else if(gesture.type==='move'){r.x=clamp(gesture.orig.x+(p.x-gesture.start.x),0,1-gesture.orig.width);r.y=clamp(gesture.orig.y+(p.y-gesture.start.y),0,1-gesture.orig.height)}else{r.width=clamp(gesture.orig.width+(p.x-gesture.start.x),.005,1-r.x);r.height=clamp(gesture.orig.height+(p.y-gesture.start.y),.005,1-r.y)}render()});
  layer.addEventListener('pointerup',e=>{if(!gesture)return;const r=rois.find(x=>x.roi_id===selectedId);if(r&&(r.width<.01||r.height<.01)){rois=rois.filter(x=>x.roi_id!==r.roi_id);selectedId=null}gesture=null;try{layer.releasePointerCapture(e.pointerId)}catch(_){}render()});
  roiList.addEventListener('click',e=>{const item=e.target.closest('.roi-item');if(item){selectedId=item.dataset.id;render()}});
  deleteSelected.addEventListener('click',()=>{if(!selectedId)return;rois=rois.filter(r=>r.roi_id!==selectedId);selectedId=null;render()});
  cameraId.addEventListener('input',render);
  copyJson.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(jsonOutput.textContent);const old=copyJson.textContent;copyJson.textContent='복사 완료';setTimeout(()=>copyJson.textContent=old,1200)}catch(_){copyJson.textContent='복사 실패'}});
  videoInput.addEventListener('change',()=>{const file=videoInput.files&&videoInput.files[0];if(!file)return;if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=URL.createObjectURL(file);video.src=objectUrl;video.style.display='block';empty.style.display='none';video.load()});
  video.addEventListener('loadedmetadata',()=>{layer.classList.add('ready');syncVideoRect()});window.addEventListener('resize',syncVideoRect);render();
})();
