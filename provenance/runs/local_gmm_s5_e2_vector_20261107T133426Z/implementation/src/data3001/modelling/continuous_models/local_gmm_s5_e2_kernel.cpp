// Same constrained two-dimensional EM as local_gmm_s5_e2.py.
// This kernel only fuses arithmetic loops; it has no RNG, I/O or model selection.
#include <algorithm>
#include <cmath>
#include <vector>
#include <Accelerate/Accelerate.h>

namespace {
bool expectation(const double* z, int n, int K, const double* w,
                 const double* a, const double* b, std::vector<double>& r, double& ll) {
    double lognorm[3], inv[3][3];
    for (int k=0;k<K;++k) {
        const double* c=b+4*k;
        double det=c[0]*c[3]-c[1]*c[2];
        if (!(det>0 && w[k]>0) || !std::isfinite(det)) return false;
        lognorm[k]=std::log(w[k])-std::log(2*std::acos(-1.))-.5*std::log(det);
        inv[k][0]=c[3]/det; inv[k][1]=c[1]/det; inv[k][2]=c[0]/det;
    }
    std::vector<double> maxima(n), sums(n), logs(n);
    for (int i=0;i<n;++i) {
        double maximum=-INFINITY;
        for (int k=0;k<K;++k) {
            double x=z[2*i]-a[2*k], y=z[2*i+1]-a[2*k+1];
            r[i*K+k]=lognorm[k]-.5*(inv[k][0]*x*x+inv[k][2]*y*y-2*inv[k][1]*x*y);
            maximum=std::max(maximum,r[i*K+k]);
        }
        if (!std::isfinite(maximum)) return false;
        maxima[i]=maximum;
        for (int k=0;k<K;++k) r[i*K+k]-=maximum;
    }
    int count=n*K;vvexp(r.data(),r.data(),&count);
    for(int i=0;i<n;++i) {
        double sum=0;for(int k=0;k<K;++k)sum+=r[i*K+k];
        if(!(sum>0))return false;
        sums[i]=sum;
        for(int k=0;k<K;++k)r[i*K+k]/=sum;
    }
    vvlog(logs.data(),sums.data(),&n);
    long double total=0;
    for(int i=0;i<n;++i)total+=maxima[i]+logs[i];
    ll=double(total/n); return std::isfinite(ll);
}

bool maximize(const double* z,int n,int K,const std::vector<double>& r,
              double* w,double* a,double* b) {
    double counts[3]={0,0,0};
    std::fill(a,a+2*K,0.);
    for (int i=0;i<n;++i) for (int k=0;k<K;++k) {
        double v=r[i*K+k]; counts[k]+=v; a[2*k]+=v*z[2*i];a[2*k+1]+=v*z[2*i+1];
    }
    for (int k=0;k<K;++k) {
        if (!(counts[k]>0)) return false;
        w[k]=counts[k]/n;a[2*k]/=counts[k];a[2*k+1]/=counts[k];
    }
    std::fill(b,b+4*K,0.);
    for (int i=0;i<n;++i) for (int k=0;k<K;++k) {
        double v=r[i*K+k],x=z[2*i]-a[2*k],y=z[2*i+1]-a[2*k+1];
        b[4*k]+=v*x*x;b[4*k+1]+=v*x*y;b[4*k+3]+=v*y*y;
    }
    for (int k=0;k<K;++k) {
        double x=b[4*k]/counts[k],y=b[4*k+1]/counts[k],d=b[4*k+3]/counts[k];
        double mid=(x+d)/2,rad=std::hypot((x-d)/2,y),lo=mid-rad,hi=mid+rad;
        if (lo<.01) {
            double angle=.5*std::atan2(2*y,x-d),c=std::cos(angle),s=std::sin(angle);
            hi=std::max(hi,.01);lo=std::max(lo,.01);
            x=hi*c*c+lo*s*s;d=hi*s*s+lo*c*c;y=(hi-lo)*s*c;
        }
        b[4*k]=x;b[4*k+1]=b[4*k+2]=y;b[4*k+3]=d;
    }
    return true;
}

double residual(const double* a,const double* b,int size) {
    double scale=1,delta=0;
    for(int i=0;i<size;++i){scale=std::max(scale,std::abs(a[i]));delta=std::max(delta,std::abs(a[i]-b[i]));}
    return delta/scale;
}
}

extern "C" int e2_em(const double* z,int n,int K,int max_iter,double* w,double* a,double* b,
                      double* trace,int* iterations,double* fixed) {
    if (n<3 || K<2 || K>3 || max_iter!=200) return 5;
    std::vector<double> r(n*K);double ll=0;
    if(!expectation(z,n,K,w,a,b,r,ll))return 3;
    trace[0]=ll;int stable=0;*fixed=INFINITY;
    double nw[3],na[6],nb[12];
    for(int it=1;it<=max_iter;++it) {
        *iterations=it;
        if(!maximize(z,n,K,r,nw,na,nb))return 2;
        double next;
        if(!expectation(z,n,K,nw,na,nb,r,next))return 3;
        double delta=next-ll;
        if(delta < -1e-10)return 4;
        stable=(delta<=1e-6)?stable+1:0;
        std::copy(nw,nw+K,w);std::copy(na,na+2*K,a);std::copy(nb,nb+4*K,b);
        ll=next;trace[it]=ll;
        if(stable>=5 || it==max_iter) {
            if(!maximize(z,n,K,r,nw,na,nb))return 2;
            *fixed=std::max({residual(w,nw,K),residual(a,na,2*K),residual(b,nb,4*K)});
            if(stable>=5 && *fixed<=1e-4)return 0;
        }
    }
    return 1;
}
