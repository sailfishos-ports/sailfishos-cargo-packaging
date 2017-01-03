# Only x86_64 and i686 are Tier 1 platforms at this time.
# https://forge.rust-lang.org/platform-support.html
%global rust_arches x86_64 i686 armv7hl aarch64 ppc64 ppc64le s390x

# To bootstrap from scratch, set the date from src/snapshots.txt
# e.g. 0.11.0 wants 2016-03-21
%global bootstrap_date 2016-11-02
# (using a newer version than required to get vendor directories and more archs)

# Only the specified arches will use bootstrap binaries.
#global bootstrap_arches %%{rust_arches}

Name:           cargo
Version:        0.15.0
Release:        2%{?dist}
Summary:        Rust's package manager and build tool
License:        ASL 2.0 or MIT
URL:            https://crates.io/
ExclusiveArch:  %{rust_arches}

Source0:        https://github.com/rust-lang/%{name}/archive/%{version}/%{name}-%{version}.tar.gz

# submodule, bundled for local installation only, not distributed
%global rust_installer 4f994850808a572e2cc8d43f968893c8e942e9bf
Source1:        https://github.com/rust-lang/rust-installer/archive/%{rust_installer}/rust-installer-%{rust_installer}.tar.gz

# Get the Rust triple for any arch.
%{lua: function rust_triple(arch)
  local abi = "gnu"
  if arch == "armv7hl" then
    arch = "armv7"
    abi = "gnueabihf"
  elseif arch == "ppc64" then
    arch = "powerpc64"
  elseif arch == "ppc64le" then
    arch = "powerpc64le"
  end
  return arch.."-unknown-linux-"..abi
end}

%global rust_triple %{lua: print(rust_triple(rpm.expand("%{_target_cpu}")))}

%if %defined bootstrap_arches
# For each bootstrap arch, add an additional binary Source.
# Also define bootstrap_source just for the current target.
%{lua: do
  local bootstrap_arches = {}
  for arch in string.gmatch(rpm.expand("%{bootstrap_arches}"), "%S+") do
    table.insert(bootstrap_arches, arch)
  end
  local base = rpm.expand("https://static.rust-lang.org/cargo-dist"
                          .."/%{bootstrap_date}/cargo-nightly")
  local target_arch = rpm.expand("%{_target_cpu}")
  for i, arch in ipairs(bootstrap_arches) do
    i = i + 10
    print(string.format("Source%d: %s-%s.tar.gz\n",
                        i, base, rust_triple(arch)))
    if arch == target_arch then
      rpm.define("bootstrap_source "..i)
    end
  end
end}
%endif

# Use vendored crate dependencies so we can build offline.
# Created using https://github.com/alexcrichton/cargo-vendor/ 0.1.3
# It's so big because some of the -sys crates include the C library source they
# want to link to.  With our -devel buildreqs in place, they'll be used instead.
# FIXME: These should all eventually be packaged on their own!
Source100:      %{name}-%{version}-vendor.tar.xz

BuildRequires:  rust
BuildRequires:  make
BuildRequires:  cmake
BuildRequires:  gcc
BuildRequires:  python2 >= 2.7
BuildRequires:  curl

%ifarch %{bootstrap_arches}
%global bootstrap_root cargo-nightly-%{rust_triple}
%global local_cargo %{_builddir}/%{bootstrap_root}/cargo/bin/cargo
%else
BuildRequires:  %{name} >= 0.13.0
%global local_cargo %{_bindir}/%{name}
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

%ifarch %{bootstrap_arches}
%setup -q -n %{bootstrap_root} -T -b %{bootstrap_source}
test -f '%{local_cargo}'
%endif

# vendored crates
%setup -q -n %{name}-%{version}-vendor -T -b 100

# cargo sources
%setup -q

# rust-installer
%setup -q -T -D -a 1
rmdir src/rust-installer
mv rust-installer-%{rust_installer} src/rust-installer

mkdir -p .cargo
cat >.cargo/config <<EOF
[source.crates-io]
registry = 'https://github.com/rust-lang/crates.io-index'
replace-with = 'vendored-sources'

[source.vendored-sources]
directory = '$PWD/../%{name}-%{version}-vendor'
EOF


%build

%ifarch aarch64 %{mips} %{power64}
%ifarch %{bootstrap_arches}
# Upstream binaries have a 4k-paged jemalloc, which breaks with Fedora 64k pages.
# See https://github.com/rust-lang/rust/issues/36994
# Fixed by https://github.com/rust-lang/rust/issues/37392
# So we can remove this when bootstrap reaches Rust 1.14.0, Cargo ~0.15.0.
export MALLOC_CONF=lg_dirty_mult:-1
%endif
%endif

# convince libgit2-sys to use the distro libgit2
export LIBGIT2_SYS_USE_PKG_CONFIG=1

# use our offline registry
mkdir -p .cargo
export CARGO_HOME=$PWD/.cargo

# This should eventually migrate to distro policy
# Enable optimization, debuginfo, and link hardening.
export RUSTFLAGS="-C opt-level=3 -g -Clink-args=-Wl,-z,relro,-z,now"

%configure --disable-option-checking \
  --build=%{rust_triple} --host=%{rust_triple} --target=%{rust_triple} \
  --rustc=%{_bindir}/rustc --rustdoc=%{_bindir}/rustdoc \
  --cargo=%{local_cargo} \
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
