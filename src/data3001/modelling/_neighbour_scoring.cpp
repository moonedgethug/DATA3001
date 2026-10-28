// Literal scalar implementation of the independently tested stratified score.
// No fast-math, no model inference, no filesystem/network/data access.
#include <algorithm>
#include <cstdint>
#include <numeric>
#include <vector>
extern "C" int neighbour_scores(int n,int m,int q,int r,int stride,
 const int32_t* d,const int32_t* truth,const uint8_t* k,const uint8_t* l,
 const double* table,double* out) {
 if(n<1||m<2||q<1||r<2||m%r)return 1;
 const int proposals=m/r;
 for(int row=0;row<n;++row){
  auto w=[&](int i){int z=row*m+i;return table+(int(k[z])*stride+int(l[z]))*q;};
  std::vector<int> order(m);std::iota(order.begin(),order.end(),0);
  std::sort(order.begin(),order.end(),[&](int a,int b){return d[row*m+a]<d[row*m+b];});
  std::vector<double> mass(q,0),py(q,0),u(q,0),e(q,0),norm(q,0),bc(q,0),bu(q,0),group(q);
  for(int z=0;z<m;){
   int end=z+1;while(end<m&&d[row*m+order[z]]==d[row*m+order[end]])++end;
   std::fill(group.begin(),group.end(),0.);
   for(int a=z;a<end;++a){const double* v=w(order[a]);for(int j=0;j<q;++j)group[j]+=v[j];}
   int dest=d[row*m+order[z]];
   for(int j=0;j<q;++j){double g=group[j]/m;norm[j]+=g*g;mass[j]+=g;
    if(dest==truth[row])py[j]+=g;if(dest==-3)u[j]+=g;if(dest==-2)e[j]+=g;}
   z=end;
  }
  std::vector<double> sm(q),sy(q),s2(q),bad2(q),sn(q);std::vector<int> small(r);
  for(int s=0;s<proposals;++s){
   std::fill(sm.begin(),sm.end(),0.);std::fill(sy.begin(),sy.end(),0.);
   std::fill(s2.begin(),s2.end(),0.);std::fill(bad2.begin(),bad2.end(),0.);std::fill(sn.begin(),sn.end(),0.);
   for(int a=0;a<r;++a){int ia=s*r+a;const double* v=w(ia);bool match=d[row*m+ia]==truth[row];
    for(int j=0;j<q;++j){sm[j]+=v[j];if(match)sy[j]+=v[j];s2[j]+=v[j]*v[j];if(!match)bad2[j]+=2*v[j]*v[j];}
   }
   std::iota(small.begin(),small.end(),s*r);
   std::sort(small.begin(),small.end(),[&](int a,int b){return d[row*m+a]<d[row*m+b];});
   for(int z=0;z<r;){int end=z+1;while(end<r&&d[row*m+small[z]]==d[row*m+small[end]])++end;
    std::fill(group.begin(),group.end(),0.);
    for(int a=z;a<end;++a){const double* v=w(small[a]);for(int j=0;j<q;++j)group[j]+=v[j];}
    for(int j=0;j<q;++j)sn[j]+=group[j]*group[j];z=end;}
   for(int j=0;j<q;++j){double mean=sm[j]/r,hit=sy[j]/r,ns=sn[j]/(double(r)*r);
    bu[j]+=(s2[j]/r-ns)/(r-1.0)/(proposals*proposals);
    bc[j]+=(bad2[j]/r-(ns-2*mean*hit+mean*mean))/(r-1.0)/(proposals*proposals);}
  }
  for(int j=0;j<q;++j){int base=row*6*q+j;
   out[base]=norm[j]-2*mass[j]*py[j]+mass[j]*mass[j]-bc[j];
   out[base+q]=1-2*py[j]+norm[j]-bu[j];out[base+2*q]=mass[j];out[base+3*q]=py[j];
   out[base+4*q]=u[j];out[base+5*q]=e[j];}
 }
 return 0;
}
