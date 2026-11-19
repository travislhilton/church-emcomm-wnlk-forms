// QR (Quick Response) code generator for the printed handouts: byte mode, error correction level M, versions 1-10.
// The encoder is copied from forms/qr-posters.html (itself from eoc/EOC_Wall_Display.html): no library, no internet.
  var QR=(function(){
    var EXP=[],LOG=[]; (function(){ var x=1; for(var i=0;i<255;i++){ EXP[i]=x; LOG[x]=i; x<<=1; if(x&256) x^=0x11D; } for(var i=255;i<512;i++) EXP[i]=EXP[i-255]; })();
    function mul(a,b){ return (a&&b)?EXP[LOG[a]+LOG[b]]:0; }
    function genPoly(n){ var g=[1]; for(var i=0;i<n;i++){ var ng=new Array(g.length+1); for(var k=0;k<ng.length;k++) ng[k]=0; for(var j=0;j<g.length;j++){ ng[j]^=g[j]; ng[j+1]^=mul(g[j],EXP[i]); } g=ng; } return g; }
    function rsEC(data,n){ var g=genPoly(n), r=[]; for(var k=0;k<n;k++) r.push(0); for(var i=0;i<data.length;i++){ var f=data[i]^r[0]; r.shift(); r.push(0); if(f) for(var j=0;j<n;j++) r[j]^=mul(g[j+1],f); } return r; }
    // per version (EC level M): [EC codewords per block, [[blocks, data codewords per block], ...]]
    var BLK=[null,[10,[[1,16]]],[16,[[1,28]]],[26,[[1,44]]],[18,[[2,32]]],[24,[[2,43]]],[16,[[4,27]]],[18,[[4,31]]],[22,[[2,38],[2,39]]],[22,[[3,36],[2,37]]],[26,[[4,43],[1,44]]]];
    var ALIGN=[null,[],[6,18],[6,22],[6,26],[6,30],[6,34],[6,22,38],[6,24,42],[6,26,46],[6,28,50]];
    var MASK=[function(r,c){return (r+c)%2===0;},function(r,c){return r%2===0;},function(r,c){return c%3===0;},function(r,c){return (r+c)%3===0;},
              function(r,c){return (Math.floor(r/2)+Math.floor(c/3))%2===0;},function(r,c){return (r*c)%2+(r*c)%3===0;},
              function(r,c){return ((r*c)%2+(r*c)%3)%2===0;},function(r,c){return ((r+c)%2+(r*c)%3)%2===0;}];
    function fmtBits(mask){ var d=mask; var r=d<<10; for(var i=14;i>=10;i--) if(r&(1<<i)) r^=0x537<<(i-10); return ((d<<10)|r)^0x5412; }
    function verBits(v){ var r=v<<12; for(var i=17;i>=12;i--) if(r&(1<<i)) r^=0x1F25<<(i-12); return (v<<12)|r; }
    function penalty(g,N){ var p=0,r,c,k,run;
      for(r=0;r<N;r++){ run=1; for(c=1;c<N;c++){ if(g[r][c]===g[r][c-1]){ run++; if(run===5) p+=3; else if(run>5) p++; } else run=1; } }
      for(c=0;c<N;c++){ run=1; for(r=1;r<N;r++){ if(g[r][c]===g[r-1][c]){ run++; if(run===5) p+=3; else if(run>5) p++; } else run=1; } }
      for(r=0;r<N-1;r++) for(c=0;c<N-1;c++){ var s=g[r][c]+g[r][c+1]+g[r+1][c]+g[r+1][c+1]; if(s===0||s===4) p+=3; }
      var P1=[1,0,1,1,1,0,1,0,0,0,0], P2=[0,0,0,0,1,0,1,1,1,0,1];
      for(r=0;r<N;r++) for(c=0;c<=N-11;c++){ var a=true,b=true,a2=true,b2=true; for(k=0;k<11;k++){ if(g[r][c+k]!==P1[k]) a=false; if(g[r][c+k]!==P2[k]) b=false; if(g[c+k][r]!==P1[k]) a2=false; if(g[c+k][r]!==P2[k]) b2=false; } if(a||b) p+=40; if(a2||b2) p+=40; }
      var dark=0; for(r=0;r<N;r++) for(c=0;c<N;c++) dark+=g[r][c]; var pct=dark*100/(N*N), prev=Math.floor(pct/5)*5; p+=Math.min(Math.abs(prev-50),Math.abs(prev+5-50))/5*10; return p; }
    return function(text, forceMask){
      var bytes=Array.prototype.slice.call(new TextEncoder().encode(text)), v, cap, i, j, r, c;
      for(v=1;v<=10;v++){ cap=0; BLK[v][1].forEach(function(b){cap+=b[0]*b[1];}); if(bytes.length+(v<10?2:3)<=cap) break; }
      if(v>10) return null;
      var bits=[]; function put(val,len){ for(var k=len-1;k>=0;k--) bits.push((val>>k)&1); }
      put(4,4); put(bytes.length, v<10?8:16); bytes.forEach(function(b){ put(b,8); });
      for(i=0;i<4&&bits.length<cap*8;i++) bits.push(0); while(bits.length%8) bits.push(0);
      var data=[]; for(i=0;i<bits.length;i+=8){ var by=0; for(j=0;j<8;j++) by=(by<<1)|bits[i+j]; data.push(by); }
      for(i=0;data.length<cap;i++) data.push(i%2?0x11:0xEC);
      var ecn=BLK[v][0], blocks=[], ecs=[], pos=0;
      BLK[v][1].forEach(function(b){ for(var k=0;k<b[0];k++){ var d=data.slice(pos,pos+b[1]); pos+=b[1]; blocks.push(d); ecs.push(rsEC(d,ecn)); } });
      var out=[], maxD=0; blocks.forEach(function(b){ if(b.length>maxD) maxD=b.length; });
      for(i=0;i<maxD;i++) blocks.forEach(function(b){ if(i<b.length) out.push(b[i]); });
      for(i=0;i<ecn;i++) ecs.forEach(function(e){ out.push(e[i]); });
      var N=v*4+17, m=[], fn=[]; for(r=0;r<N;r++){ var mr=[], fr=[]; for(c=0;c<N;c++){ mr.push(0); fr.push(false); } m.push(mr); fn.push(fr); }
      function set(rr,cc,val){ if(rr<0||cc<0||rr>=N||cc>=N) return; m[rr][cc]=val?1:0; fn[rr][cc]=true; }
      function finder(r0,c0){ for(var a=-1;a<=7;a++) for(var b=-1;b<=7;b++){ var on=(a>=0&&a<=6&&b>=0&&b<=6)&&(a===0||a===6||b===0||b===6||(a>=2&&a<=4&&b>=2&&b<=4)); set(r0+a,c0+b,on); } }
      finder(0,0); finder(0,N-7); finder(N-7,0);
      for(i=8;i<N-8;i++){ set(6,i,i%2===0); set(i,6,i%2===0); }
      ALIGN[v].forEach(function(ar){ ALIGN[v].forEach(function(ac){ if((ar<=8&&ac<=8)||(ar<=8&&ac>=N-9)||(ar>=N-9&&ac<=8)) return; for(var dr=-2;dr<=2;dr++) for(var dc=-2;dc<=2;dc++) set(ar+dr,ac+dc, Math.max(Math.abs(dr),Math.abs(dc))!==1); }); });
      set(4*v+9,8,true);
      for(i=0;i<9;i++){ fn[8][i]=true; fn[i][8]=true; }
      for(i=N-8;i<N;i++) fn[8][i]=true; for(i=N-7;i<N;i++) fn[i][8]=true;
      if(v>=7){ for(i=0;i<6;i++) for(j=N-11;j<=N-9;j++){ fn[i][j]=true; fn[j][i]=true; } }
      var bi=0, dir=-1, row=N-1;
      for(var col=N-1;col>0;col-=2){ if(col===6) col--;
        while(true){ for(c=0;c<2;c++){ var cc=col-c; if(!fn[row][cc]){ var byte=out[bi>>3]; m[row][cc]=(byte===undefined)?0:(byte>>(7-(bi&7)))&1; bi++; } }
          row+=dir; if(row<0||row>=N){ row-=dir; dir=-dir; break; } } }
      var best=null, bestP=Infinity;
      for(var mk=0;mk<8;mk++){ if(forceMask!=null&&mk!==forceMask) continue; var g=m.map(function(rw){ return rw.slice(); });
        for(r=0;r<N;r++) for(c=0;c<N;c++) if(!fn[r][c]&&MASK[mk](r,c)) g[r][c]^=1;
        var f=fmtBits(mk);
        for(i=0;i<15;i++){ var b=(f>>(14-i))&1;
          if(i<6) g[8][i]=b; else if(i===6) g[8][7]=b; else if(i===7) g[8][8]=b; else if(i===8) g[7][8]=b; else g[14-i][8]=b;
          if(i<7) g[N-1-i][8]=b; else g[8][N-15+i]=b; }
        if(v>=7){ var vi=verBits(v); for(i=0;i<18;i++){ var vb=(vi>>i)&1; g[Math.floor(i/3)][N-11+i%3]=vb; g[N-11+i%3][Math.floor(i/3)]=vb; } }
        var p=penalty(g,N); if(p<bestP){ bestP=p; best=g; } }
      return best;
    };
  })();

// Draw every element with class "qr" and a data-url attribute as an SVG (vector: sharp at any print size).
// data-dark sets the module colour (default black); the quiet zone is 4 modules of white.
function drawQRs() {
  var els = document.querySelectorAll('.qr[data-url]');
  for (var i = 0; i < els.length; i++) {
    var el = els[i], url = el.getAttribute('data-url'), dark = el.getAttribute('data-dark') || '#000';
    var g = QR(url); if (!g) { el.textContent = 'QR error'; continue; }
    var N = g.length, q = 4, W = N + 2 * q, d = '';
    for (var r = 0; r < N; r++) for (var c = 0; c < N; c++) if (g[r][c]) d += 'M' + (c + q) + ' ' + (r + q) + 'h1v1h-1z';
    el.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + W + '" shape-rendering="crispEdges" role="img" aria-label="QR code: ' + url + '">'
      + '<rect width="' + W + '" height="' + W + '" fill="#fff"/><path d="' + d + '" fill="' + dark + '"/></svg>';
  }
}
document.addEventListener('DOMContentLoaded', drawQRs);
