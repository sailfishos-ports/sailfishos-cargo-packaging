# Only x86_64 and i686 are Tier 1 platforms at this time.
# https://forge.rust-lang.org/platform-support.html
%global rust_arches x86_64 i686 armv7hl aarch64 ppc64 ppc64le s390x

# Only the specified arches will use bootstrap binaries.
#global bootstrap_arches %%{rust_arches}

%if 0%{?rhel}
%bcond_without bundled_libgit2
%else
%bcond_with bundled_libgit2
%endif

Name:           cargo
Version:        0.19.0
Release:        1%{?dist}
Summary:        Rust's package manager and build tool
License:        ASL 2.0 or MIT
URL:            https://crates.io/
ExclusiveArch:  %{rust_arches}

%global cargo_version %{version}
%global cargo_bootstrap 0.18.0

Source0:        https://github.com/rust-lang/%{name}/archive/%{cargo_version}/%{name}-%{cargo_version}.tar.gz

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
  local base = rpm.expand("https://static.rust-lang.org/dist/cargo-%{cargo_bootstrap}")
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
# Created using https://github.com/alexcrichton/cargo-vendor/ 0.1.7
# It's so big because some of the -sys crates include the C library source they
# want to link to.  With our -devel buildreqs in place, they'll be used instead.
# FIXME: These should all eventually be packaged on their own!
Source100:      %{name}-%{version}-vendor.tar.xz

BuildRequires:  rust
BuildRequires:  make
BuildRequires:  cmake
BuildRequires:  gcc

%ifarch %{bootstrap_arches}
%global bootstrap_root cargo-%{cargo_bootstrap}-%{rust_triple}
%global local_cargo %{_builddir}/%{bootstrap_root}/cargo/bin/cargo
%else
BuildRequires:  %{name} >= 0.13.0
%global local_cargo %{_bindir}/%{name}
%endif

# Indirect dependencies for vendored -sys crates above
BuildRequires:  libcurl-devel
BuildRequires:  libssh2-devel
BuildRequires:  openssl-devel
BuildRequires:  zlib-devel
BuildRequires:  pkgconfig

%if %with bundled_libgit2
Provides:       bundled(libgit2) = 0.24.0
%else
BuildRequires:  libgit2-devel >= 0.24
%endif

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
%setup -q -n %{name}-%{cargo_version}

# rust-installer
%setup -q -n %{name}-%{cargo_version} -T -D -a 1
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

%if %without bundled_libgit2
# convince libgit2-sys to use the distro libgit2
export LIBGIT2_SYS_USE_PKG_CONFIG=1
%endif

# use our offline registry
mkdir -p .cargo
export CARGO_HOME=$PWD/.cargo

# This should eventually migrate to distro policy
# Enable optimization, debuginfo, and link hardening.
export RUSTFLAGS="-C opt-level=3 -g -Clink-arg=-Wl,-z,relro,-z,now"

%configure --disable-option-checking \
  --build=%{rust_triple} --host=%{rust_triple} --target=%{rust_triple} \
  --rustc=%{_bindir}/rustc --rustdoc=%{_bindir}/rustdoc \
  --cargo=%{local_cargo} \
  --release-channel=stable \
  %{nil}

%make_build %{!?rhel:-Onone}


%install
%make_install

# Remove installer artifacts (manifests, uninstall scripts, etc.)
rm -rv %{buildroot}/%{_prefix}/lib/

# Fix the etc/ location
mv -v %{buildroot}/%{_prefix}/%{_sysconfdir} %{buildroot}/%{_sysconfdir}

# Remove unwanted documentation files (we already package them)
rm -rf %{buildroot}/%{_docdir}/%{name}/


%check
# the tests are more oriented toward in-tree contributors
#make test


%files
%license LICENSE-APACHE LICENSE-MIT LICENSE-THIRD-PARTY
%doc README.md
%{_bindir}/cargo
%{_mandir}/man1/cargo*.1*
%{_sysconfdir}/bash_completion.d/cargo
%{_datadir}/zsh/site-functions/_cargo


%changelog
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
