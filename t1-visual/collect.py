import pathlib, subprocess, re, json, datetime, collections, hashlib

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=True)
SRC = pathlib.Path('/root/t1-lab/src/qemu-6.2.0')
QEMU = '/opt/qemu-6.2.0/bin/qemu-system-x86_64'

def run(args, **kw):
    return subprocess.run(args, text=True, capture_output=True, **kw)

# Real-mode boot sector: print KVM! to debugcon, then exit via isa-debug-exit.
code = bytes.fromhex('b04be6e9 b056e6e9 b04de6e9 b021e6e9 baf400 b010 ee fa f4 ebfc')
(OUT/'boot.bin').write_bytes(code.ljust(510, b'\0') + b'\x55\xaa')
(OUT/'events.txt').write_text('kvm_run_exit\nkvm_set_user_memory\n')
cmd = ['strace','-f','-tt','-yy','-s','256','-e','trace=openat,ioctl,mmap',
       '-o',str(OUT/'syscalls.log'), QEMU,'-machine','pc,accel=kvm','-cpu','host',
       '-smp','1','-m','16','-display','none','-serial','none','-monitor','none',
       '-nic','none','-no-reboot','-drive',f'file={OUT}/boot.bin,format=raw,if=floppy,readonly=on',
       '-boot','a','-debugcon',f'file:{OUT}/guest-output.txt',
       '-device','isa-debug-exit,iobase=0xf4,iosize=0x04',
       '-trace',f'events={OUT}/events.txt,file={OUT}/qemu-trace.log']
try:
    result = run(cmd, timeout=30)
    rc, stderr = result.returncode, result.stderr
except subprocess.TimeoutExpired:
    rc, stderr = -1, 'Timed out after 30 seconds'
(OUT/'stderr.txt').write_text(stderr)
raw = (OUT/'syscalls.log').read_text(errors='replace')
counts = collections.Counter(re.findall(r'ioctl\([^\n]*?, (KVM_[A-Z0-9_]+)',raw))
source_files = ['accel/kvm/kvm-all.c','accel/kvm/kvm-accel-ops.c','target/i386/kvm/kvm.c','linux-headers/linux/kvm.h']
sources = []
keys = ['KVM_GET_API_VERSION','KVM_CHECK_EXTENSION','KVM_CREATE_VM','KVM_CREATE_VCPU',
        'KVM_GET_VCPU_MMAP_SIZE','KVM_SET_USER_MEMORY_REGION','KVM_SET_REGS',
        'KVM_SET_SREGS','KVM_RUN','KVM_EXIT_IO','KVM_EXIT_MMIO',
        'kvm_arch_put_registers','kvm_arch_get_registers','kvm_cpu_exec','kvm_init_vcpu']
for name in source_files:
    p = SRC/name
    if not p.exists(): continue
    body = p.read_text(errors='replace')
    hits = [{'line':i,'text':s.strip()} for i,s in enumerate(body.splitlines(),1) if any(k in s for k in keys)]
    sources.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'hits':hits})
output = (OUT/'guest-output.txt').read_text(errors='replace') if (OUT/'guest-output.txt').exists() else ''
trace = (OUT/'qemu-trace.log').read_text(errors='replace') if (OUT/'qemu-trace.log').exists() else ''
live = run(['pgrep','-af','/opt/qemu-6.2.0/bin/qemu-system']).stdout
data = {'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'kernel':run(['uname','-r']).stdout.strip(),'version':run([QEMU,'--version']).stdout.splitlines()[0],
        'command':cmd,'returncode':rc,'passed':rc==33 and output=='KVM!',
        'guest_output':output,'counts':dict(counts),'sources':sources,
        'exits':dict(collections.Counter(re.findall(r'kvm_run_exit[^\n]*reason (\d+)',trace))),
        'trace_tail':trace.splitlines()[-50:], 'running_qemu':live,
        'syscall_sample':[s for s in raw.splitlines() if 'KVM_' in s][:100]}
(ROOT/'evidence.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(ROOT/'evidence.js').write_text('window.T1_EVIDENCE = '+json.dumps(data,ensure_ascii=False)+';')
print(json.dumps({k:data[k] for k in ['passed','returncode','guest_output','counts','exits']},indent=2))
raise SystemExit(0 if data['passed'] else 1)
