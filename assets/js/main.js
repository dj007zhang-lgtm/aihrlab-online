window.addEventListener('error', function(ev){try{console.error('[AIHR main.js] runtime error:', ev.error||ev.message);}catch(_){}});
function trackEvent(name,params={}){if(typeof gtag!=='undefined'){gtag('event',name,{...params,send_to:'G-BWLGRVRRGN'});}}try{
(function initScrollTracking(){const milestones=[25,50,75,90,100];const fired=new Set();let maxDepth=0;function getScrollPct(){const h=document.documentElement;const scrollTop=window.scrollY||h.scrollTop;const scrollHeight=h.scrollHeight-h.clientHeight;if(scrollHeight<=0)return 0;return Math.round((scrollTop/scrollHeight)*100);}function checkScroll(){const pct=getScrollPct();if(pct>maxDepth)maxDepth=pct;for(const m of milestones){if(pct>=m&&!fired.has(m)){fired.add(m);trackEvent('scroll_depth',{percent:m,page_path:window.location.pathname,page_title:document.title});}}}function initArticleBottomTracking(){const bottom=document.querySelector('.article-qrcode, .article-body');if(!bottom)return;const observer=new IntersectionObserver((entries)=>{entries.forEach(entry=>{if(entry.isIntersecting&&!fired.has('article_end')){fired.add('article_end');trackEvent('article_end_view',{page_path:window.location.pathname,max_scroll_depth:maxDepth});}});},{threshold:0.3});observer.observe(bottom);}window.addEventListener('scroll',throttle(checkScroll,500),{passive:true});window.addEventListener('load',()=>{checkScroll();initArticleBottomTracking();});document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'){trackEvent('page_engagement',{page_path:window.location.pathname,max_scroll_depth:maxDepth,engaged_time_sec:Math.round((Date.now()-loadTime)/1000)});}});})();
}catch(e){console.error('[AIHR main.js] module 0 init failed:', e);}
const loadTime=Date.now();let engagedSeconds=0;let engagementTimer=null;function startEngagementTimer(){if(engagementTimer)return;engagementTimer=setInterval(()=>{engagedSeconds++;if(engagedSeconds%30===0){trackEvent('engagement_ping',{page_path:window.location.pathname,engaged_seconds:engagedSeconds});}},1000);}function stopEngagementTimer(){clearInterval(engagementTimer);engagementTimer=null;}document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){startEngagementTimer();}else{stopEngagementTimer();trackEvent('engagement_pause',{page_path:window.location.pathname,total_engaged_seconds:engagedSeconds});}});window.addEventListener('load',startEngagementTimer);window.addEventListener('beforeunload',()=>{stopEngagementTimer();trackEvent('page_exit',{page_path:window.location.pathname,total_engaged_seconds:engagedSeconds,max_scroll_depth:Math.round((window.scrollY/(document.documentElement.scrollHeight-document.documentElement.clientHeight))*100)||0});});function initQRCTATracking(){const qrSection=document.querySelector('.article-qrcode, .article-footer-qr, #oaQr');if(qrSection){const observer=new IntersectionObserver((entries)=>{entries.forEach(entry=>{if(entry.isIntersecting){trackEvent('qr_code_view',{page_path:window.location.pathname,cta_variant:localStorage.getItem('qr_cta_variant')||'A'});observer.disconnect();}});},{threshold:0.5});observer.observe(qrSection);const qrImg=qrSection.querySelector('img');if(qrImg){qrImg.style.cursor='pointer';qrImg.addEventListener('click',()=>{trackEvent('qr_code_click',{page_path:window.location.pathname,cta_variant:localStorage.getItem('qr_cta_variant')||'A'});});qrSection.addEventListener('contextmenu',()=>{trackEvent('qr_code_click',{page_path:window.location.pathname,cta_variant:localStorage.getItem('qr_cta_variant')||'A',action:'longpress'});});}}const followSection=document.getElementById('follow');if(followSection){const observer=new IntersectionObserver((entries)=>{entries.forEach(entry=>{if(entry.isIntersecting){trackEvent('follow_section_view',{page_path:window.location.pathname});observer.disconnect();}});},{threshold:0.3});observer.observe(followSection);}}const ABTests={qr_cta:{name:'qr_cta',variants:[{id:'A',cta:'这篇文章的分析框架，会在公众号持续更新。',hint:'关注后回复 <code>关键词</code> 获取配套工具'},{id:'B',cta:'同类深度分析，公众号每周更新。',hint:'关注后回复 <code>关键词</code> 获取文章配套工具'}],getVariant(){let stored=localStorage.getItem('ab_qr_cta');if(stored)return JSON.parse(stored);const variant=this.variants[Math.random()<0.5?0:1];localStorage.setItem('ab_qr_cta',JSON.stringify(variant));return variant;},apply(){const v=this.getVariant();localStorage.setItem('qr_cta_variant',v.id);const qrSection=document.querySelector('.article-qrcode');if(qrSection){const ctaP=qrSection.querySelector('p:first-child');const hintP=qrSection.querySelector('.qr-hint');if(ctaP)ctaP.innerHTML=v.cta;if(hintP)hintP.innerHTML=v.hint;}trackEvent('ab_test_exposure',{test_name:'qr_cta',variant:v.id,page_path:window.location.pathname});}}};function initArticleCardTracking(){document.querySelectorAll('.article-card a[href]').forEach(card=>{card.addEventListener('click',(e)=>{const articleCard=card.closest('.article-card');const title=articleCard?.querySelector('h3')?.textContent||'';trackEvent('article_card_click',{article_title:title,page_path:window.location.pathname,link_url:card.href||card.getAttribute('href')});});});}function throttle(fn,wait){let last=0;return function(...args){const now=Date.now();if(now-last>=wait){last=now;fn.apply(this,args);}};}document.addEventListener('DOMContentLoaded',()=>{const navToggle=document.querySelector('.nav-toggle');const siteNav=document.querySelector('.site-nav');if(navToggle&&siteNav){navToggle.addEventListener('click',()=>{siteNav.classList.toggle('open');});siteNav.querySelectorAll('a').forEach(link=>{link.addEventListener('click',()=>siteNav.classList.remove('open'));});}const currentPath=window.location.pathname;siteNav?.querySelectorAll('a').forEach(link=>{const href=link.getAttribute('href');if(href&&href!=='/'&&currentPath.includes(href.replace(/\/$/,''))){link.classList.add('active');}if(href==='/'&&(currentPath==='/'||currentPath.endsWith('index.html'))){link.classList.add('active');}});document.querySelectorAll('a[href^="#"]').forEach(anchor=>{anchor.addEventListener('click',(e)=>{const target=document.querySelector(anchor.getAttribute('href'));if(target){e.preventDefault();target.scrollIntoView({behavior:'smooth',block:'start'});}});});initQRCTATracking();initArticleCardTracking();if(document.querySelector('.article-qrcode')){ABTests.qr_cta.apply();}if(!localStorage.getItem('returning_visitor')){trackEvent('first_visit',{page_path:window.location.pathname});localStorage.setItem('returning_visitor','true');}(function(){var overlay=document.createElement('div');overlay.className='gate-overlay';overlay.id='gate-overlay';overlay.innerHTML='<div class="gate-modal">'+'<div class="gate-modal-header">'+'<h3 id="gate-title">获取资源</h3>'+'<p>关注公众号「AIHR数智引擎」，回复关键词获取下载链接</p>'+'</div>'+'<div class="gate-modal-body">'+'<div class="gate-qrcode-wrap">'+'<img src="/assets/images/qrcode-wechat.jpg" alt="关注公众号">'+'</div>'+'<p class="gate-instruction" id="gate-instruction"></p>'+'</div>'+'<div class="gate-modal-footer">'+'<button class="gate-close-btn" id="gate-close">我知道了</button>'+'</div>'+'</div>';document.body.appendChild(overlay);var closeBtn=document.getElementById('gate-close');function closeModal(){overlay.classList.remove('open');}overlay.addEventListener('click',function(e){if(e.target===overlay)closeModal();});if(closeBtn)closeBtn.addEventListener('click',closeModal);document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});document.querySelectorAll('.gate-trigger').forEach(function(btn){btn.addEventListener('click',function(){var title=this.dataset.gateTitle||'获取资源';var instruction=this.dataset.gateInstruction||'';document.getElementById('gate-title').textContent=title;var instEl=document.getElementById('gate-instruction');if(instEl)instEl.innerHTML=instruction;overlay.classList.add('open');if(typeof trackEvent==='function'){trackEvent('gate_open',{resource_name:title,page_path:window.location.pathname});}});});})();});try{
(function(){var overlay=null;function createOverlay(){overlay=document.createElement('div');overlay.className='gate-overlay';overlay.id='gate-overlay';overlay.innerHTML='<div class="gate-modal">'+'<div class="gate-modal-header">'+'<h3 id="gate-title">获取资源</h3>'+'<p>关注公众号「AIHR数智引擎」，回复关键词获取下载链接</p>'+'</div>'+'<div class="gate-modal-body">'+'<div class="gate-qrcode-wrap">'+'<img src="/assets/images/qrcode-wechat.jpg" alt="关注公众号 AIHR数智引擎">'+'</div>'+'<p class="gate-instruction" id="gate-instruction"></p>'+'</div>'+'<div class="gate-modal-footer">'+'<button class="gate-close-btn" id="gate-close">我知道了</button>'+'</div>'+'</div>';document.body.appendChild(overlay);var closeBtn=document.getElementById('gate-close');function closeModal(){overlay.classList.remove('open');}overlay.addEventListener('click',function(e){if(e.target===overlay)closeModal();});if(closeBtn)closeBtn.addEventListener('click',closeModal);document.addEventListener('keydown',function(e){if(e.key==='Escape')closeModal();});}window.openGate=function(btn){if(!overlay)createOverlay();var title=(btn&&btn.dataset&&btn.dataset.gateTitle)?btn.dataset.gateTitle:'获取资源';var instruction=(btn&&btn.dataset&&btn.dataset.gateInstruction)?btn.dataset.gateInstruction:'';var titleEl=document.getElementById('gate-title');var instEl=document.getElementById('gate-instruction');if(titleEl)titleEl.textContent=title;if(instEl)instEl.innerHTML=instruction;overlay.classList.add('open');if(typeof trackEvent==='function'){trackEvent('gate_open',{resource_name:title,page_path:window.location.pathname});}};})();
}catch(e){console.error('[AIHR main.js] module 1 init failed:', e);}


/* ===== 阅读体验重构（2026-07-17）：文章页互动组件 + 阅读进度条 ===== */
try{
(function(){
  var STORE_KEY='aihr_engage_v1';
  var ICONS={
    like:'<svg viewBox="0 0 24 24" class="eng-ic"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>',
    collect:'<svg viewBox="0 0 24 24" class="eng-ic"><path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/></svg>',
    share:'<svg viewBox="0 0 24 24" class="eng-ic"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>'
  };
  var LABELS={like:['认同','已认同'],collect:['收藏','已收藏'],share:['分享','分享']};
  function getStore(){try{return JSON.parse(localStorage.getItem(STORE_KEY)||'{}');}catch(e){return {};}}
  function setStore(s){try{localStorage.setItem(STORE_KEY,JSON.stringify(s));}catch(e){}}
  function slugFromPath(){var p=location.pathname.split('/articles/')[1];return p?p.replace(/\.html$/,'') : location.pathname;}
  function btnHtml(type){var lab=LABELS[type][0];return '<button class="eg-btn" data-engage="'+type+'" type="button" aria-label="'+lab+'">'+ICONS[type]+'<span class="eg-label">'+lab+'</span></button>';}
  function slugOf(el){var c=el.closest('[data-slug]');return c?c.getAttribute('data-slug'):slugFromPath();}
  function applyState(btn,store){var type=btn.getAttribute('data-engage');var slug=slugOf(btn);var s=store[slug]||{};if(type==='like'){btn.classList.toggle('liked',!!s.like);btn.querySelector('.eg-label').textContent=s.like?LABELS.like[1]:LABELS.like[0];}if(type==='collect'){btn.classList.toggle('collected',!!s.collect);btn.querySelector('.eg-label').textContent=s.collect?LABELS.collect[1]:LABELS.collect[0];}}
  function restoreAll(store){document.querySelectorAll('[data-engage]').forEach(function(b){applyState(b,store);});}
  document.addEventListener('click',function(e){
    var btn=e.target.closest('[data-engage]');if(!btn)return;
    var type=btn.getAttribute('data-engage');
    if(type==='share'){
      var url=location.href,title=document.title;
      if(navigator.share){navigator.share({title:title,url:url}).catch(function(){});}
      else if(navigator.clipboard){navigator.clipboard.writeText(url).then(function(){var l=btn.querySelector('.eg-label');var o=l.textContent;l.textContent='链接已复制';setTimeout(function(){l.textContent=o;},1500);});}
      return;
    }
    var slug=slugOf(btn);var store=getStore();var s=store[slug]||{like:false,collect:false};
    if(type==='like'){s.like=!s.like;btn.classList.toggle('liked',s.like);btn.querySelector('.eg-label').textContent=s.like?LABELS.like[1]:LABELS.like[0];}
    if(type==='collect'){s.collect=!s.collect;btn.classList.toggle('collected',s.collect);btn.querySelector('.eg-label').textContent=s.collect?LABELS.collect[1]:LABELS.collect[0];}
    store[slug]=s;setStore(store);
  });
  if(document.querySelector('.article-content-wrapper')){
    var qr=document.querySelector('.article-footer-qr');
    if(qr && !document.querySelector('.article-engagement')){
      var eng=document.createElement('div');eng.className='article-engagement';eng.setAttribute('data-slug',slugFromPath());
      eng.innerHTML=btnHtml('like')+btnHtml('collect')+btnHtml('share');
      qr.parentNode.insertBefore(eng,qr);
    }
    var bar=document.createElement('div');bar.className='reading-progress';document.body.prepend(bar);
    function upd(){var h=document.documentElement;var max=h.scrollHeight-h.clientHeight;var p=max>0?(window.scrollY||h.scrollTop)/max*100:0;bar.style.width=(p>100?100:p)+'%';}
    window.addEventListener('scroll',upd,{passive:true});window.addEventListener('load',upd);upd();
  }
  restoreAll(getStore());
})();
}catch(e){console.error('[AIHR main.js] module 2 init failed:', e);}


/* ===== 文章列表页：分类筛选（2026-07-18） ===== */
try{
(function(){
  var grid=document.getElementById('article-grid');
  if(!grid)return; /* 非列表页不执行 */
  var cards=grid.querySelectorAll('.article-card');
  var btns=document.querySelectorAll('.filter-btn');

  /* 动态填充数量徽章 */
  var counts={all:cards.length};
  cards.forEach(function(c){
    var cat=c.getAttribute('data-category')||'';
    counts[cat]=(counts[cat]||0)+1;
  });
  btns.forEach(function(b){
    var f=b.getAttribute('data-filter')||'all';
    if(counts[f]!==undefined){
      var sp=document.createElement('span');
      sp.className='filter-count';
      sp.textContent=counts[f];
      b.appendChild(sp);
    }
  });

  window.filterArticles=function(category,clickedBtn){
    btns.forEach(function(b){b.classList.remove('active');});
    if(clickedBtn)clickedBtn.classList.add('active');
    cards.forEach(function(card){
      if(category==='all'||card.getAttribute('data-category')===category){
        card.style.display='';
        card.style.opacity='1';
        card.style.transform='translateY(0)';
      }else{
        card.style.opacity='0';
        card.style.transform='translateY(8px)';
        setTimeout(function(){card.style.display='none';},200);
      }
    });
  };
})();
}catch(e){console.error('[AIHR main.js] module 3 init failed:', e);}


/* ===== 四好迭代 #1：TOC 导航增强（桌面当前章节高亮 + 移动端目录抽屉） ===== */
try{
(function(){
  var rail=document.querySelector('.toc-rail');
  if(!rail)return;
  var links=Array.prototype.slice.call(rail.querySelectorAll('.toc li a[href^="#"]'));
  if(!links.length)return;
  var map={},sections=[];
  links.forEach(function(a){
    var id=a.getAttribute('href').slice(1);
    var sec=id&&document.getElementById(id);
    if(sec){map[id]=a;sections.push(sec);}
  });
  if(!sections.length)return;
  /* 桌面：当前章节高亮 */
  function highlight(){
    var picked=null;
    for(var i=0;i<sections.length;i++){
      if(sections[i].getBoundingClientRect().top<=110){picked=sections[i];}else{break;}
    }
    if(!picked)picked=sections[0];
    links.forEach(function(a){a.classList.remove('active');});
    if(picked&&map[picked.id])map[picked.id].classList.add('active');
  }
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(highlight,{rootMargin:'-80px 0px -70% 0px',threshold:[0,1]});
    sections.forEach(function(s){io.observe(s);});
  }
  highlight();
  /* 移动端：底部抽屉 + 浮动按钮 */
  var mq=window.matchMedia('(max-width:1180px)');
  var fab=document.createElement('button');
  fab.className='toc-fab';fab.type='button';fab.setAttribute('aria-label','打开目录');
  fab.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>目录';
  var backdrop=document.createElement('div');backdrop.className='toc-backdrop';
  function openDrawer(){if(!mq.matches)return;rail.classList.add('open');backdrop.classList.add('show');}
  function closeDrawer(){rail.classList.remove('open');backdrop.classList.remove('show');}
  fab.addEventListener('click',function(){rail.classList.contains('open')?closeDrawer():openDrawer();});
  backdrop.addEventListener('click',closeDrawer);
  rail.querySelectorAll('a').forEach(function(a){a.addEventListener('click',closeDrawer);});
  var h4=rail.querySelector('.toc h4');if(h4){h4.addEventListener('click',closeDrawer);}
  document.body.appendChild(backdrop);document.body.appendChild(fab);
})();
}catch(e){console.error('[AIHR main.js] module 4 init failed:', e);}


/* ===== 二维码唯一运行时护栏（2026-08-05） =====
   若页面同时存在文章底部二维码与站点页脚二维码，隐藏页脚二维码，
   确保用户不会在同一页看到两个公众号二维码。此护栏不能替代质量门，
   仅作为最后一道用户体验兜底。 */
try{
(function(){
  if(document.querySelector('.article-footer-qr')){
    document.querySelectorAll('.footer-col--qr').forEach(function(el){
      el.style.display='none';
      console.warn('[AIHR] 已隐藏页脚重复二维码；请在 HTML 中删除 .footer-col--qr 以根治。');
    });
  }
})();
}catch(e){console.error('[AIHR main.js] module 5 init failed:', e);}

/* ===== R2：读者字号调节（2026-08-08） ===== */
/* 缩放 html font-size 以级联全部 rem 排版；偏好存入 localStorage；控件注入 .site-nav。
   单模块故障被 try/catch 隔离，不影响其余功能。 */
try{
(function(){
  var KEY='aihr_fontsize';
  var MIN=14, MAX=20, DEF=17, STEP=1;
  function clamp(v){return Math.max(MIN,Math.min(MAX,v));}
  function current(){var s=parseInt(localStorage.getItem(KEY),10);return (s>=MIN&&s<=MAX)?s:DEF;}
  function apply(size){document.documentElement.style.fontSize=size+'px';}
  apply(current());
  var nav=document.querySelector('.site-nav');
  if(!nav)return;
  var ctrl=document.createElement('div');
  ctrl.className='font-size-control';
  ctrl.setAttribute('role','group');
  ctrl.setAttribute('aria-label','调节正文字号');
  ctrl.innerHTML='<button class="fs-btn" data-fs="dec" type="button" aria-label="减小字号" title="减小字号">A−</button>'+
                 '<span class="fs-val" aria-live="polite">'+current()+'</span>'+
                 '<button class="fs-btn" data-fs="inc" type="button" aria-label="增大字号" title="增大字号">A+</button>';
  var search=nav.querySelector('.nav-search-btn');
  if(search){nav.insertBefore(ctrl,search);}else{nav.appendChild(ctrl);}
  function refresh(){var v=ctrl.querySelector('.fs-val');if(v)v.textContent=current();}
  ctrl.addEventListener('click',function(e){
    var b=e.target.closest('[data-fs]');if(!b)return;
    var delta=(b.getAttribute('data-fs')==='inc')?STEP:-STEP;
    var next=clamp(current()+delta);
    if(next!==current()){localStorage.setItem(KEY,String(next));apply(next);refresh();}
  });
})();
}catch(e){console.error('[AIHR main.js] module 6 init failed:', e);}

/* ===== R1：深色模式切换（2026-08-08） ===== */
/* 复用 R2 注入点 .site-nav；偏好存 localStorage['aihr_theme']；与 head 防闪脚本同源。
   单模块故障被 try/catch 隔离，不影响其余功能。 */
try{
(function(){
  var KEY='aihr_theme';
  function applyTheme(t){document.documentElement.setAttribute('data-theme',t);}
  function current(){return document.documentElement.getAttribute('data-theme')||'light';}
  function persist(t){try{localStorage.setItem(KEY,t);}catch(e){}}
  applyTheme(current());
  var nav=document.querySelector('.site-nav');
  if(!nav)return;
  var ctrl=document.createElement('div');
  ctrl.className='font-size-control';
  ctrl.setAttribute('role','group');
  ctrl.setAttribute('aria-label','切换深色或浅色模式');
  var btn=document.createElement('button');
  btn.className='theme-toggle';btn.type='button';
  function label(){return current()==='dark'?'浅色':'深色';}
  function aria(){return '切换到'+(current()==='dark'?'浅色':'深色')+'模式';}
  btn.textContent=label();btn.setAttribute('aria-label',aria());btn.title=aria();
  ctrl.appendChild(btn);
  var search=nav.querySelector('.nav-search-btn');
  if(search){nav.insertBefore(ctrl,search);}else{nav.appendChild(ctrl);}
  btn.addEventListener('click',function(){
    var next=current()==='dark'?'light':'dark';
    applyTheme(next);persist(next);
    btn.textContent=label();btn.setAttribute('aria-label',aria());btn.title=aria();
  });
})();
}catch(e){console.error('[AIHR main.js] module 7 init failed:', e);}

