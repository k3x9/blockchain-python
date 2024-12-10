#include<bits/stdc++.h>
using namespace std;
using namespace std::chrono;

typedef long long ll;
typedef unsigned long long ull;
#define vk vector<ll>
#define vkv vector<vector<ll>>
#define vkp vector<pair<ll,ll>>
#define all(v) v.begin(), v.end()

const ll N=1e9 + 7;

bool cmp(pair<ll,ll> a, pair<ll,ll> b) {
    if (a.first != b.first) return a.first < b.first;
    return a.second > b.second;
}
bool cmp2(pair<ll,ll> a, pair<ll,ll> b) {
    return a.second > b.second;
}
bool cmp3(ll a, ll b) {
    return a > b;
}
bool cmp4(pair<ll,ll> a, pair<ll,ll> b) {
    if (a.second != b.second) return a.second > b.second;
    return a.first > b.first;
}

template<typename T>
void print_vec(vector<T> &v) {
    for (auto i : v) {
        cout << i << " ";
    }
    cout << "\n";
}

template<typename T1, typename T2>
void print_vecp(vector<pair<T1,T2>> &v) {
    for (auto i : v) {
        cout << i.first << " " << i.second << "\n";
    }
}

template<typename T>
void print_vecv(vector<vector<T>> &v) {
    for (auto i : v) {
        for (auto j : i) {
            cout << j << " ";
        }
        cout << "\n";
    }
}

ll power(ll a, ll b) {
    a %= N;
    b %= N;
    if (b == 0) return 1;
    if (b == 1) return a;
    ll res = power(a, b / 2);
    if (b % 2 == 0) {
        ll ans = (res) * (res) % N;
        return ans;
    }
    ll ans = (res) * (res) % N;
    ans = ans * a % N;
    return ans;
}

ll check(ll i, ll j, ll n, ll m) {
    return i >= 0 && i < n && j >= 0 && j < m;
}

ll lcm(ll a, ll b) {
    return min(a, b) * (max(a, b) / __gcd(a, b));
}

void print(ll a[], ll l, ll h) {
    for (ll i = l; i < h; i++) {
        cout << a[i] << " ";
    }
    cout << "\n";
}

template<typename T>
void print_set(set<T> &s) {
    for (auto i : s) {
        cout << i << " ";
    }
    cout << "\n";
}

bool preProcess = true;
void pre() {
    if (preProcess) {
        // Preprocessing
    }
    preProcess = false;
}

void solve() {
    
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    cout.tie(NULL);
    int t = 1;
    cin >> t;
    for (int i = 1; i <= t; ++i) {
        solve();
    }
    return 0;
}