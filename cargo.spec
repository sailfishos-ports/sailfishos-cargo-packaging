# To bootstrap from scratch, set the date from src/snapshots.txt
# e.g. 0.11.0 wants 2016-03-21
%bcond_without bootstrap
%global bootstrap_date 2016-03-21

Name:           cargo
Version:        0.13.0
Release:        2%{?dist}
Summary:        Rust's package manager and build tool
License:        ASL 2.0 or MIT
URL:            https://crates.io/

Source0:        https://github.com/rust-lang/%{name}/archive/%{version}/%{name}-%{version}.tar.gz

# submodule, bundled for local installation only, not distributed
%global rust_installer c37d3747da75c280237dc2d6b925078e69555499
Source1:        https://github.com/rust-lang/rust-installer/archive/%{rust_installer}/rust-installer-%{rust_installer}.tar.gz

%if %with bootstrap
%global bootstrap_dist https://static.rust-lang.org/cargo-dist
%global bootstrap_base %{bootstrap_dist}/%{bootstrap_date}/%{name}-nightly
Source10:       %{bootstrap_base}-x86_64-unknown-linux-gnu.tar.gz
Source11:       %{bootstrap_base}-i686-unknown-linux-gnu.tar.gz
# "unofficial" snapshots below for new architectures
Source12:       %{bootstrap_dist}/2016-03-25/%{name}-nightly-armv7-unknown-linux-gnueabihf.tar.gz
Source13:       %{bootstrap_dist}/2016-04-05/%{name}-nightly-aarch64-unknown-linux-gnu.tar.gz
%endif

# Use vendored crate dependencies so we can build offline.
# Created using https://github.com/alexcrichton/cargo-vendor/
# It's so big because some of the -sys crates include the C library source they
# want to link to.  With our -devel buildreqs in place, they'll be used instead.
# FIXME: These should all eventually be packaged on their own!
# (needs directory registries, https://github.com/rust-lang/cargo/pull/2857)
# (directory registries are now in 0.13.0, but bootstrap doesn't support it yet.)
Source100:      %{name}-%{version}-vendor.tar.xz

# Only x86_64 and i686 are Tier 1 platforms at this time.
ExclusiveArch:  x86_64 i686 armv7hl aarch64
%ifarch armv7hl
%global rust_triple armv7-unknown-linux-gnueabihf
%else
%global rust_triple %{_target_cpu}-unknown-linux-gnu
%endif

BuildRequires:  rust
BuildRequires:  make
BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  python
BuildRequires:  curl
BuildRequires:  git

%if %without bootstrap
BuildRequires:  %{name}
%global local_cargo %{_bindir}/%{name}
%else
%global bootstrap_root cargo-nightly-%{rust_triple}
%global local_cargo %{_builddir}/%{name}-%{version}/%{bootstrap_root}/cargo/bin/cargo
%endif

# Indirect dependencies for vendored -sys crates above
BuildRequires:  libcurl-devel
BuildRequires:  libgit2-devel
BuildRequires:  libssh2-devel
BuildRequires:  openssl-devel
BuildRequires:  zlib-devel
BuildRequires:  pkgconfig

# Cargo is not much use without Rust
Requires:       rust

%description
Cargo is a tool that allows Rust projects to declare their various dependencies
and ensure that you'll always get a repeatable build.


%prep
%setup -q

# rust-installer
%setup -q -T -D -a 1
rmdir src/rust-installer
mv rust-installer-%{rust_installer} src/rust-installer

# vendored crates
%setup -q -T -D -a 100
pushd vendor/index
sed -i.vendor -e "s#file://.*/vendor/#file://$PWD/../#g" config.json
git config user.name "Cargo Packagers"
git config user.email cargo-owner@fedoraproject.org
git commit -m "builddir patched" config.json
popd

%if %with bootstrap
find %{sources} -name '%{bootstrap_root}.tar.gz' -exec tar -xvzf '{}' ';'
test -f '%{local_cargo}'
%endif


%build

%ifarch aarch64
%if %with bootstrap
# Upstream binaries have a 4k-paged jemalloc, which breaks with Fedora 64k pages.
# https://github.com/rust-lang/rust/issues/36994
export MALLOC_CONF=lg_dirty_mult:-1
%endif
%endif

# convince libgit2-sys to use the distro libgit2
export LIBGIT2_SYS_USE_PKG_CONFIG=1

# use our offline registry
mkdir -p .cargo
export CARGO_HOME=$PWD/.cargo
export CARGO_REGISTRY_INDEX="file://$PWD/vendor/index"

# this should eventually migrate to distro policy
# (disabling MIR due to https://github.com/rust-lang/rust/issues/36774)
export RUSTFLAGS="-C opt-level=3 -g -Zorbit=no"

%configure --disable-option-checking \
  --build=%{rust_triple} --host=%{rust_triple} --target=%{rust_triple} \
  --local-cargo=%{local_cargo} \
  --local-rust-root=%{_prefix} \
  %{nil}

%make_build VERBOSE=1


%install
%make_install VERBOSE=1

# Remove installer artifacts (manifests, uninstall scripts, etc.)
rm -rv %{buildroot}/%{_prefix}/lib/

# Fix the etc/ location
mv -v %{buildroot}/%{_prefix}/%{_sysconfdir} %{buildroot}/%{_sysconfdir}

# Remove unwanted documentation files (we already package them)
rm -rf %{buildroot}/%{_docdir}/%{name}/


%check
# the tests are more oriented toward in-tree contributors
#make test VERBOSE=1


%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig


%files
%license LICENSE-APACHE LICENSE-MIT LICENSE-THIRD-PARTY
%doc README.md
%{_bindir}/cargo
%{_mandir}/man1/cargo*.1*
%{_sysconfdir}/bash_completion.d/cargo
%{_datadir}/zsh/site-functions/_cargo


%changelog
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
