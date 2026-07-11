# DonglelandCore 통합 노트 (검증 완료 · 2026-07-12)

동글랜드 런처가 DonglelandCore(클라이언트 코어 모드)를 **Fabric 위에서, 서버의 미허용 모드
검사에 안 잡히게** 붙이는 방법. **런처 테스트베드 3.0.1 + 실서버(dongleland.com)에서 완전 동작 검증됨.**

## 요구와 해법 요약

| 요구 | 해법 |
|---|---|
| 기능은 바닐라처럼 (패킷 미변조) | Java Agent(ASM)로 훅만 삽입. 회전 등 패킷 미발생 |
| 서버 미허용 모드 검사 통과 | **mods/ 아님 + fabric.mod.json 없음 → Fabric 모드 목록에 안 잡힘** |
| Fabric 로더의 다른 모드(Xaero/Iris 등)도 사용 | **Fabric 프로필로 실행** (installed_version_id 그대로) |
| Knot 클래스로더 격리로 인한 크래시 | agent가 `addToClassPath`로 우리 jar를 **Knot 클래스패스에 추가** |

## 정확한 실행 방식 (`launcher.py`)

Fabric 프로필로 실행하되, 코어 jar는 **`-javaagent`로만** 붙인다. mods/에는 절대 넣지 않는다.

```python
# build_command 의 options
"jvmArguments": [f"-Xmx{max_mem_mb}M", *_core_mod_jvm_args()],

def _core_mod_jvm_args():
    jar = <런처폴더>/dongleland-core.jar
    return [f"-javaagent:{jar}", f"-Ddongleland.dir={instance.instance_dir()}"]
```

- `-Ddongleland.dir=<인스턴스>` → 로그(`dongleland-core.log`)·설정(`mod_config.json`)이 인스턴스 폴더에 생성.
- **version_id 는 Fabric 프로필**(`fabric-loader-...-26.1.2`). 바닐라로 바꾸지 않는다(다른 모드 로드 위해).
- mods/ 배치 코드·`fabric.mod.json`·`disableClassPathIsolation` 플래그는 **쓰지 않는다**(아래 함정 참조).

## 왜 이렇게밖에 안 되는가 (시행착오 로그 — 반복 금지)

1. **mods/에 jar + fabric.mod.json** → 동작하지만 **Fabric 모드 목록에 등록 → 서버 검사에 걸림.** ❌
2. **-javaagent만 (그냥)** → `NoClassDefFoundError: kr/dongleland/core/Hooks — hasn't been exposed to the game`.
   Knot(Fabric 클래스로더)이 시스템 클래스패스의 우리 클래스를 게임에 노출하지 않음. ❌
3. **-Dfabric.debug.disableClassPathIsolation=true** → `LinkageError: loader constraint violation`.
   격리를 풀면 Knot이 우리 클래스를 **'app'(시스템) 로더에 위임** → 우리 Hooks(app)가 보는
   `net.minecraft.*`가 게임(knot)이 쓰는 사본과 **달라서** 첫 훅 호출에서 충돌. ❌
4. **addToClassPath로 Knot 클래스패스에 추가** → ✅ **정답.**
   Knot이 우리 클래스를 **직접 로드** → `net.minecraft.*` 참조가 게임과 동일 사본. 모드 등록 아님.

## 정답 메커니즘 (`kr.dongleland.core.agent.KnotExposure`, 코어 모드 쪽)

`CoreTransformer.transform()` 최상단에서, `loader`(변환 대상 클래스의 로더)의 클래스명에
`knot`이 포함되면 **1회**:

```java
Path jar = KnotExposure.class.getProtectionDomain().getCodeSource().getLocation() 로 우리 jar 경로;
FabricLauncherBase.getLauncher().addToClassPath(jar);  // Fabric 공식 API, 리플렉션 호출
```

- Fabric 공식 `FabricLauncher.addToClassPath(Path, String...)` — **클래스패스 추가일 뿐 모드 등록이 아님** → 모드 목록 미노출.
- 바닐라(로더 없음) 환경에선 `knot` 미검출 → **no-op** (runDev 등 그대로 동작).
- premain(app 로더)에서는 Config/Hooks/features를 **건드리지 않는다.** 그래야 우리 클래스가
  Knot에서만 로드돼 사본이 갈라지지 않는다.

## 검증된 로그 지표

`dongleland-core.log` 정상 시:
```
[INFO] agent starting ...
[INFO] agent loaded - targets (active: H1..H10)
[INFO] transformed net/minecraft/... [Hx]        (대상 클래스 로드 시)
[INFO] exposed core jar to Knot classpath: ...    (Fabric 위에서만)
```
`classloaders - Minecraft=knot... Hooks=knot...` → 둘 다 knot이면 완벽.

## 버전 갱신(26.2 등) 시

1. 코어 모드에서 `docs/HOOKS.md` 갱신(javap로 시그니처 확인).
2. 시그니처 불일치 훅은 부팅 로그에 `HOOK MISSING:` → 그 기능만 비활성(게임/타 훅 무관, R1).
3. jar 재빌드 → 런처 폴더의 `dongleland-core.jar` 교체.

## 배포 시 주의

- 코어 jar에는 **fabric.mod.json이 없어야** 한다(무흔적). 있으면 mods/ 오배치 시 검사에 걸림.
- 코어 jar는 런처와 함께 배포하고, 실행 시 `-javaagent`로만 붙인다.
