%ifarch %ix86
%global rust_triple i686-unknown-linux-gnu
%else
%global rust_triple armv7-unknown-linux-gnueabihf
%endif

Name:           cargo023
Version:        0.23.0
Release:        2
Summary:        Rust's package manager and build tool
License:        ASL 2.0 or MIT
URL:            https://crates.io/
ExclusiveArch:  i486 armv7hl

Source0:        https://github.com/rust-lang/cargo/archive/%{version}/cargo-%{version}.tar.gz
Patch1:         cargo-0.23.0-disable-mdbook.patch

# Use vendored crate dependencies so we can build offline.
# Created using https://github.com/alexcrichton/cargo-vendor/ 0.1.13
# It's so big because some of the -sys crates include the C library source they
# want to link to.  With our -devel buildreqs in place, they'll be used instead.
# FIXME: These should all eventually be packaged on their own!
Source100:      cargo-%{version}-vendor.tar.gz

BuildRequires:  rust122
BuildRequires:  rust122-std-static
BuildRequires:  cargo022
BuildRequires:  make
BuildRequires:  cmake
BuildRequires:  gcc

# Indirect dependencies for vendored -sys crates above
BuildRequires:  libcurl-devel
BuildRequires:  libssh2-devel
BuildRequires:  openssl-devel
BuildRequires:  zlib-devel
BuildRequires:  pkgconfig

# Cargo is not much use without Rust
# Requires:       rust

%description
Cargo is a tool that allows Rust projects to declare their various dependencies
and ensure that you'll always get a repeatable build.


%package doc
Summary:        Documentation for Cargo
BuildArch:      noarch

%description doc
This package includes HTML documentation for Cargo.


%prep
# cargo sources
%setup -q -n cargo-%{version}
tar -xzf %SOURCE100

%patch1 -p1 -b .disable-mdbook

# define the offline registry
%global cargo_home $PWD/.cargo
mkdir -p %{cargo_home}
cat >.cargo/config <<EOF
[source.crates-io]
registry = 'https://github.com/rust-lang/crates.io-index'
replace-with = 'vendored-sources'

[source.vendored-sources]
directory = '$PWD/vendor'
EOF

# This should eventually migrate to distro policy
# Enable optimization, debuginfo, and link hardening.
%global rustflags -Copt-level=3 -Cdebuginfo=2 -Clink-arg=-Wl,-z,relro,-z,now

# use our offline registry and custom rustc flags
export CARGO_HOME="%{cargo_home}"
export RUSTFLAGS="%{rustflags}"

# cargo no longer uses a configure script, but we still want to use
# CFLAGS in case of the odd C file in vendored dependencies.
%{?__global_cflags:export CFLAGS="%{__global_cflags}"}
%{!?__global_cflags:%{?optflags:export CFLAGS="%{optflags}"}}
%{?__global_ldflags:export LDFLAGS="%{__global_ldflags}"}

/usr/bin/cargo build --release
sh src/ci/dox.sh


%install
export CARGO_HOME="%{cargo_home}"
export RUSTFLAGS="%{rustflags}"

/usr/bin/cargo install --root %{buildroot}%{_prefix}
rm %{buildroot}%{_prefix}/.crates.toml

mkdir -p %{buildroot}%{_mandir}/man1
%{__install} -p -m644 src/etc/man/cargo*.1 \
  -t %{buildroot}%{_mandir}/man1

mkdir -p %{buildroot}%{_sysconfdir}/bash_completion.d/cargo
%{__install} -p -m644 src/etc/cargo.bashcomp.sh \
  -D %{buildroot}%{_sysconfdir}/bash_completion.d/cargo

mkdir -p %{buildroot}%{_datadir}/zsh/site-functions/_cargo
%{__install} -p -m644 src/etc/_cargo \
  -D %{buildroot}%{_datadir}/zsh/site-functions/_cargo

# Create the path for crate-devel packages
mkdir -p %{buildroot}%{_datadir}/cargo/registry

mkdir -p %{buildroot}%{_docdir}/cargo
cp -a target/doc %{buildroot}%{_docdir}/cargo/html


%check
export CARGO_HOME="%{cargo_home}"
export RUSTFLAGS="%{rustflags}"

%ifarch %ix86
# some tests are known to fail exact output due to libgit2 differences
CFG_DISABLE_CROSS_TESTS=1 /usr/bin/cargo test --no-fail-fast || :
%endif

%files
%{_bindir}/cargo
%{_mandir}/man1/cargo*.1*
%{_sysconfdir}/bash_completion.d/cargo
%{_datadir}/zsh/site-functions/_cargo
%dir %{_datadir}/cargo
%dir %{_datadir}/cargo/registry

%files doc
%{_docdir}/cargo/html


%changelog
* Sat Jan 6 2018 Lucien Xu <sfietkonstantin@free.fr> - 0.23.0-2
- Packaging based on Fedora package

* Wed Nov 29 2017 Josh Stone <jistone@redhat.com> - 0.23.0-1
- Update to 0.23.0.

* Mon Oct 16 2017 Josh Stone <jistone@redhat.com> - 0.22.0-1
- Update to 0.22.0.

* Mon Sep 11 2017 Josh Stone <jistone@redhat.com> - 0.21.1-1
- Update to 0.21.1.

* Thu Aug 31 2017 Josh Stone <jistone@redhat.com> - 0.21.0-1
- Update to 0.21.0.

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.20.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.20.0-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Jul 21 2017 Josh Stone <jistone@redhat.com> - 0.20.0-1
- Update to 0.20.0.
- Add a cargo-doc subpackage.

* Sat Jul 08 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.19.0-4
- Disable bootstrap

* Sat Jul 08 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.19.0-3
- Rebuild for libgit2 0.26.x

* Tue Jun 20 2017 Josh Stone <jistone@redhat.com> - 0.19.0-2
- Create /usr/share/cargo/registry for crate-devel packages

* Fri Jun 09 2017 Josh Stone <jistone@redhat.com> - 0.19.0-1
- Update to 0.19.0.

* Thu Apr 27 2017 Josh Stone <jistone@redhat.com> - 0.18.0-1
- Update to 0.18.0.

* Thu Mar 16 2017 Josh Stone <jistone@redhat.com> - 0.17.0-1
- Update to 0.17.0.

* Tue Feb 14 2017 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 0.16.0-2
- Backport patch to expose description in cargo metadata

* Thu Feb 09 2017 Josh Stone <jistone@redhat.com> - 0.16.0-1
- Update to 0.16.0.
- Start using the current upstream release for bootstrap.
- Merge and clean up conditionals for epel7.

* Tue Feb 07 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.15.0-4
- Disable bootstrap

* Tue Feb 07 2017 Igor Gnatenko <ignatenko@redhat.com> - 0.15.0-3
- Rebuild for libgit2-0.25.x

* Tue Jan 03 2017 Josh Stone <jistone@redhat.com> - 0.15.0-2
- Rebuild without bootstrap binaries.

* Tue Jan 03 2017 Josh Stone <jistone@redhat.com> - 0.15.0-1
- Update to 0.15.0.
- Rewrite bootstrap logic to target specific arches.
- Bootstrap ppc64, ppc64le, s390x.

* Sun Nov 13 2016 Josh Stone <jistone@redhat.com> - 0.14.0-2
- Fix CFG_RELEASE_NUM

* Thu Nov 10 2016 Josh Stone <jistone@redhat.com> - 0.14.0-1
- Update to 0.14.0.
- Use hardening flags for linking.

* Thu Oct 20 2016 Josh Stone <jistone@redhat.com> - 0.13.0-4
- Rebuild with Rust 1.12.1 and enabled MIR.

* Fri Oct 07 2016 Josh Stone <jistone@redhat.com> - 0.13.0-3
- Rebuild without bootstrap binaries.

* Thu Oct 06 2016 Josh Stone <jistone@redhat.com> - 0.13.0-2
- Bootstrap aarch64.
- Use jemalloc's MALLOC_CONF to work around #36944.

* Fri Sep 30 2016 Josh Stone <jistone@redhat.com> - 0.13.0-1
- Update to 0.13.0.
- Always use --local-cargo, even for bootstrap binaries.
- Disable MIR until rust#36774 is resolved.

* Sat Sep 03 2016 Josh Stone <jistone@redhat.com> - 0.12.0-3
- Rebuild without bootstrap binaries.

* Fri Sep 02 2016 Josh Stone <jistone@redhat.com> - 0.12.0-2
- Bootstrap armv7hl.
- Patch dl-snapshot.py to ignore hashes on unknown archs.

* Wed Aug 24 2016 Josh Stone <jistone@redhat.com> - 0.12.0-1
- Update to 0.12.0.

* Mon Aug 22 2016 Josh Stone <jistone@redhat.com> 0.11.0-3
- Rebuild without bootstrap binaries.
- Add a runtime requirement on rust.

* Mon Aug 22 2016 Josh Stone <jistone@redhat.com> - 0.11.0-2
- Initial import into Fedora (#1357749), bootstrapped

* Sun Jul 17 2016 Josh Stone <jistone@fedoraproject.org> - 0.11.0-1
- Initial package, bootstrapped
