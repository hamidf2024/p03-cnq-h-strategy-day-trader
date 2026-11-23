(function(){
var tip=document.getElementById('tip'),hm=document.getElementById('hm'),def=tip.textContent;
function show(e){var c=e.target.closest?e.target.closest('.hm-c[data-tip]'):null;if(!c)return;
 tip.textContent=c.parentNode.querySelector('.hm-name').textContent+' · '+c.getAttribute('data-tip');}
hm.addEventListener('mouseover',show);hm.addEventListener('click',show);
hm.addEventListener('mouseleave',function(){tip.textContent=def;});
var btns=document.querySelectorAll('.tabs button[data-f]'),rows=document.querySelectorAll('#score tbody tr');
Array.prototype.forEach.call(btns,function(b){b.addEventListener('click',function(){
 Array.prototype.forEach.call(btns,function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
 var f=b.getAttribute('data-f');
 Array.prototype.forEach.call(rows,function(r){r.hidden=!!f&&r.getAttribute('data-kind')!==f;});});});
})();
