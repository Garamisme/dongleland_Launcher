# 알려진 이슈

원인이 확정되지 않았거나, 우리 코드 밖에 있어 당장 고칠 수 없는 것들을 적어 둔다.
고쳐지면 이 문서에서 지운다.

---

## 서버 치장이 머리 위에 불꽃처럼 보인다 (원인 미확정)

**증상.** 서버에서 제공하는 치장을 착용하면 머리 위에 불꽃 이펙트가 뜬다.
불꽃 텍스처 뒤에 **불투명한 흰 사각형**이 함께 보인다. 바닐라 런처 등
다른 클라이언트에서는 정상으로 보인다는 제보.

**확인된 사실.**

- 코어 모드(`dongleland-core.jar`)는 무관하다. 파티클을 만드는 코드가
  떨어진 아이템 광선의 `DustParticleOptions` 하나뿐이고, 불꽃 파티클이나
  엔티티 렌더를 건드리는 코드는 없다.
- 서버 리소스팩이 커스텀 **코어 셰이더**를 싣고 있다. 게임 로그:

  ```
  [WARN] Resource pack 'server/...' indicates the following shaders
         should be ignored: rendertype_entity_translucent.fsh,
                            rendertype_entity_translucent.vsh
  ```

  이 경고는 **Sodium** 이 출력한다. 팩의 `pack.mcmeta` 에 있는
  `ignored_shaders` 목록을 읽어 찍는 것으로, 팩 제작자가 "Sodium 에서는
  이 셰이더가 적용되지 않는다"고 스스로 표시해 둔 것이다.
- 팩 안의 해당 셰이더는 **ModelEngine** 계열 경로에 들어 있다
  (`modelengine_*/assets/minecraft/shaders/core/rendertype_entity_translucent.*`).
  치장은 `hmccosmetics`·`cosmetic` 네임스페이스를 쓴다.

**유력한 설명(미검증).** 치장이 `rendertype_entity_translucent` 커스텀 셰이더에
의존하는데 Sodium 이 그걸 적용하지 않아, 알파 블렌딩이 빠진 채 렌더된다.
흰 사각형이 보이는 것은 투명해야 할 배경이 불투명하게 찍힌 모습과 일치한다.

**시도해 볼 것.**

1. [Sodium Core Shader Support](https://modrinth.com/mod/sodium-core-shader-support)
   설치 — 리소스팩이 Sodium 의 셰이더를 교체할 수 있게 한다. 26.1·Fabric·클라이언트 전용.
2. Sodium 을 잠시 제거하고 접속 — 원인이 Sodium 인지 아닌지 확실히 갈린다(확인용).

둘 중 하나로 증상이 사라지면 원인 확정. 아직 실측하지 않았다.
