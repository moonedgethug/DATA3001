// Double precision ES arithmetic, same ordered K and K*K contributions.
#include <cmath>
#include <cstddef>
extern "C" int e2_score(const double* a,const double* b,const double* truth,
                        const double* w,int K,int n,double* out){
    if(K<1 || K>3 || n<1)return 1;
    for(int j=0;j<n;++j)out[j]=0.;
    for(int k=0;k<K;++k){
        const double* p=a+static_cast<std::size_t>(k)*n*3;
        for(int j=0;j<n;++j){
            const double x=p[3*j]-truth[0],y=p[3*j+1]-truth[1],z=p[3*j+2]-truth[2];
            out[j]+=w[k]*std::sqrt((x*x+y*y)+z*z);
        }
        for(int l=0;l<K;++l){
            const double* q=b+static_cast<std::size_t>(l)*n*3;
            const double weight=(.5*w[k])*w[l];
            for(int j=0;j<n;++j){
                const double x=p[3*j]-q[3*j],y=p[3*j+1]-q[3*j+1],z=p[3*j+2]-q[3*j+2];
                out[j]-=weight*std::sqrt((x*x+y*y)+z*z);
            }
        }
    }
    for(int j=0;j<n;++j)if(!std::isfinite(out[j]))return 2;
    return 0;
}
