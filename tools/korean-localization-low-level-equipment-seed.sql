SET NAMES utf8mb4;

DELETE FROM languageitem
WHERE Language = 'KR'
  AND Tag = 'korean-localization-low-level-equipment';

INSERT INTO languageitem
  (LanguageItem_ID, TranslationId, Language, Name, Description, ExamineArticle, MessageArticle, Tag, LastTimeRowUpdated)
SELECT
  UUID(),
  it.Id_nb,
  'KR',
  CASE it.Name
    WHEN 'large round shield' THEN '대형 원형 방패'
    WHEN 'medium round shield' THEN '중형 원형 방패'
    WHEN 'large heater shield' THEN '대형 히터 방패'
    WHEN 'medium heater shield' THEN '중형 히터 방패'
    WHEN 'large block shield' THEN '대형 블록 방패'
    WHEN 'medium block shield' THEN '중형 블록 방패'
    WHEN 'elm large round shield' THEN '느릅나무 대형 원형 방패'
    WHEN 'elm medium round shield' THEN '느릅나무 중형 원형 방패'
    WHEN 'elm large heater shield' THEN '느릅나무 대형 히터 방패'
    WHEN 'elm medium heater shield' THEN '느릅나무 중형 히터 방패'
    WHEN 'elm large block shield' THEN '느릅나무 대형 블록 방패'
    WHEN 'elm medium block shield' THEN '느릅나무 중형 블록 방패'
    WHEN 'oaken large round shield' THEN '참나무 대형 원형 방패'
    WHEN 'oaken medium round shield' THEN '참나무 중형 원형 방패'
    WHEN 'oaken large heater shield' THEN '참나무 대형 히터 방패'
    WHEN 'oaken medium heater shield' THEN '참나무 중형 히터 방패'
    WHEN 'oaken large block shield' THEN '참나무 대형 블록 방패'
    WHEN 'oaken medium block shield' THEN '참나무 중형 블록 방패'
    WHEN 'hard large round shield' THEN '단단한 대형 원형 방패'
    WHEN 'hard medium round shield' THEN '단단한 중형 원형 방패'
    WHEN 'hard large heater shield' THEN '단단한 대형 히터 방패'
    WHEN 'hard medium heater shield' THEN '단단한 중형 히터 방패'
    WHEN 'hard large block shield' THEN '단단한 대형 블록 방패'
    WHEN 'hard medium block shield' THEN '단단한 중형 블록 방패'
    WHEN 'bronze short sword' THEN '청동 쇼트 소드'
    WHEN 'rowan short bow' THEN '로완 쇼트 보우'
    WHEN 'bronze two-handed sword' THEN '청동 투핸드 소드'
    WHEN 'dress robe' THEN '드레스 로브'
    WHEN 'fancy robe' THEN '화려한 로브'
    WHEN 'plain robe' THEN '평범한 로브'
    WHEN 'bronze great hammer' THEN '청동 그레이트 해머'
    WHEN 'bronze shod staff' THEN '청동 보강 스태프'
    WHEN 'bronze war hammer' THEN '청동 워 해머'
    WHEN 'bronze great sword' THEN '청동 그레이트 소드'
    WHEN 'Daring Leather Cap' THEN '대담한 가죽 모자'
    WHEN 'linen dress robe' THEN '리넨 드레스 로브'
    WHEN 'linen fancy robe' THEN '리넨 화려한 로브'
    WHEN 'linen plain robe' THEN '리넨 평범한 로브'
    WHEN 'rowan recurve bow' THEN '로완 리커브 보우'
    WHEN 'elm short bow' THEN '느릅나무 쇼트 보우'
    WHEN 'iron short sword' THEN '철 쇼트 소드'
    WHEN 'iron two-handed sword' THEN '철 투핸드 소드'
    WHEN 'iron great hammer' THEN '철 그레이트 해머'
    WHEN 'iron shod staff' THEN '철 보강 스태프'
    WHEN 'iron war hammer' THEN '철 워 해머'
    WHEN 'iron great sword' THEN '철 그레이트 소드'
    WHEN 'brocade dress robe' THEN '브로케이드 드레스 로브'
    WHEN 'brocade fancy robe' THEN '브로케이드 화려한 로브'
    WHEN 'brocade plain robe' THEN '브로케이드 평범한 로브'
    WHEN 'elm short recurve bow' THEN '느릅나무 쇼트 리커브 보우'
    WHEN 'steel short sword' THEN '강철 쇼트 소드'
    WHEN 'steel two-handed sword' THEN '강철 투핸드 소드'
    WHEN 'steel great hammer' THEN '강철 그레이트 해머'
    WHEN 'steel shod staff' THEN '강철 보강 스태프'
    WHEN 'steel war hammer' THEN '강철 워 해머'
    WHEN 'steel great sword' THEN '강철 그레이트 소드'
    WHEN 'silk dress robe' THEN '실크 드레스 로브'
    WHEN 'silk fancy robe' THEN '실크 화려한 로브'
    WHEN 'silk plain robe' THEN '실크 평범한 로브'
    WHEN 'alloy short sword' THEN '합금 쇼트 소드'
    WHEN 'ironwood short bow' THEN '아이언우드 쇼트 보우'
    WHEN 'alloy two-handed sword' THEN '합금 투핸드 소드'
    WHEN 'alloy great hammer' THEN '합금 그레이트 해머'
    WHEN 'alloy shod staff' THEN '합금 보강 스태프'
    WHEN 'alloy war hammer' THEN '합금 워 해머'
    WHEN 'alloy great sword' THEN '합금 그레이트 소드'
    WHEN 'gossamer dress robe' THEN '고사머 드레스 로브'
    WHEN 'gossamer fancy robe' THEN '고사머 화려한 로브'
    WHEN 'gossamer plain robe' THEN '고사머 평범한 로브'
    WHEN 'Tattered Worn Robe' THEN '낡고 해진 로브'
    WHEN 'two-handed sword' THEN '투핸드 소드'
    WHEN 'Rawhide Torn Sleeves' THEN '생가죽 찢어진 소매'
    WHEN 'Torn Vest' THEN '찢어진 조끼'
    WHEN 'Trapper Cloak' THEN '사냥꾼 망토'
    WHEN 'woolen dress robe' THEN '울 드레스 로브'
    WHEN 'Woolen Torn Pants' THEN '울 찢어진 바지'
    WHEN 'Woolen Torn Sleeves' THEN '울 찢어진 소매'
    WHEN 'rowan shod staff' THEN '로완 보강 스태프'
    WHEN 'two-hand spiked mace' THEN '투핸드 스파이크 메이스'
    WHEN 'great hammer' THEN '그레이트 해머'
    WHEN 'Slightly Torn Vest' THEN '살짝 찢어진 조끼'
    WHEN 'Woolen Slightly Torn Sleeves' THEN '울 살짝 찢어진 소매'
    WHEN 'Daring Leather Boots' THEN '대담한 가죽 부츠'
    WHEN 'Daring Leather Gloves' THEN '대담한 가죽 장갑'
    WHEN 'Daring Leather Jerkin' THEN '대담한 가죽 저킨'
    WHEN 'Daring Leather Leggings' THEN '대담한 가죽 레깅스'
    WHEN 'Daring Leather Sleeves' THEN '대담한 가죽 소매'
    WHEN 'Daring Padded Boots' THEN '대담한 패딩 부츠'
    WHEN 'Daring Padded Cap' THEN '대담한 패딩 모자'
    WHEN 'Daring Padded Gloves' THEN '대담한 패딩 장갑'
    WHEN 'Daring Padded Pants' THEN '대담한 패딩 바지'
    WHEN 'Daring Padded Sleeves' THEN '대담한 패딩 소매'
    WHEN 'Daring Padded Vest' THEN '대담한 패딩 조끼'
    WHEN 'Daring Studded Boots' THEN '대담한 스터디드 부츠'
    WHEN 'Daring Studded Cap' THEN '대담한 스터디드 모자'
    WHEN 'Daring Studded Gloves' THEN '대담한 스터디드 장갑'
    WHEN 'Daring Studded Jerkin' THEN '대담한 스터디드 저킨'
    WHEN 'Daring Studded Leggings' THEN '대담한 스터디드 레깅스'
    WHEN 'Daring Studded Sleeves' THEN '대담한 스터디드 소매'
    WHEN 'great sword' THEN '그레이트 소드'
    WHEN 'rowan great recurve bow' THEN '로완 그레이트 리커브 보우'
    WHEN 'rowan short recurve bow' THEN '로완 쇼트 리커브 보우'
    WHEN 'Tanned Barely Torn Cap' THEN '무두질한 살짝 찢어진 모자'
    WHEN 'elm Animist Staff of Arboreal Path' THEN '느릅나무 애니미스트 스태프: 아보리얼 패스'
    WHEN 'elm Animist Staff of Creeping Path' THEN '느릅나무 애니미스트 스태프: 크리핑 패스'
    WHEN 'elm Animist Staff of Mysticism' THEN '느릅나무 애니미스트 스태프: 미스티시즘'
    WHEN 'elm Animist Staff of Verdant Path' THEN '느릅나무 애니미스트 스태프: 버던트 패스'
    WHEN 'elm Eldritch Staff of Light' THEN '느릅나무 엘드리치 스태프: 라이트'
    WHEN 'elm Eldritch Staff of Magic' THEN '느릅나무 엘드리치 스태프: 매직'
    WHEN 'elm Eldritch Staff of Mana' THEN '느릅나무 엘드리치 스태프: 마나'
    WHEN 'elm Eldritch Staff of Void' THEN '느릅나무 엘드리치 스태프: 보이드'
    WHEN 'ferrite two-handed sword' THEN '페라이트 투핸드 소드'
    WHEN 'ferrite big shillelagh' THEN '페라이트 대형 실레일리'
    WHEN 'elm shod staff' THEN '느릅나무 보강 스태프'
    WHEN 'ferrite two-hand spiked mace' THEN '페라이트 투핸드 스파이크 메이스'
    WHEN 'ferrite great hammer' THEN '페라이트 그레이트 해머'
    WHEN 'elm great recurve bow' THEN '느릅나무 그레이트 리커브 보우'
    WHEN 'elm recurve bow' THEN '느릅나무 리커브 보우'
    WHEN 'ferrite great sword' THEN '페라이트 그레이트 소드'
    WHEN 'Midgard Spear' THEN '미드가드 스피어'
    WHEN 'Summoned Jewel' THEN '소환된 주얼'
    WHEN 'oaken Animist Staff of Arboreal Path' THEN '참나무 애니미스트 스태프: 아보리얼 패스'
    WHEN 'oaken Animist Staff of Creeping Path' THEN '참나무 애니미스트 스태프: 크리핑 패스'
    WHEN 'oaken Animist Staff of Mysticism' THEN '참나무 애니미스트 스태프: 미스티시즘'
    WHEN 'oaken Animist Staff of Verdant Path' THEN '참나무 애니미스트 스태프: 버던트 패스'
    WHEN 'oaken Eldritch Staff of Light' THEN '참나무 엘드리치 스태프: 라이트'
    WHEN 'oaken Eldritch Staff of Magic' THEN '참나무 엘드리치 스태프: 매직'
    WHEN 'oaken Eldritch Staff of Mana' THEN '참나무 엘드리치 스태프: 마나'
    WHEN 'oaken Eldritch Staff of Void' THEN '참나무 엘드리치 스태프: 보이드'
    WHEN 'quartz two-handed sword' THEN '석영 투핸드 소드'
    WHEN 'quartz big shillelagh' THEN '석영 대형 실레일리'
    WHEN 'oaken shod staff' THEN '참나무 보강 스태프'
    WHEN 'oaken short bow' THEN '참나무 쇼트 보우'
    WHEN 'quartz two-hand spiked mace' THEN '석영 투핸드 스파이크 메이스'
    WHEN 'quartz great hammer' THEN '석영 그레이트 해머'
    WHEN 'Quartz Long Sword' THEN '석영 롱 소드'
    WHEN 'Fire Hardened Irewood Spear' THEN '불로 단련한 아이어우드 스피어'
    WHEN 'oaken great recurve bow' THEN '참나무 그레이트 리커브 보우'
    WHEN 'oaken recurve bow' THEN '참나무 리커브 보우'
    WHEN 'oaken short recurve bow' THEN '참나무 쇼트 리커브 보우'
    WHEN 'quartz great sword' THEN '석영 그레이트 소드'
    WHEN 'dolomite two-handed sword' THEN '돌로마이트 투핸드 소드'
    WHEN 'ironwood Animist Staff of Arboreal Path' THEN '아이언우드 애니미스트 스태프: 아보리얼 패스'
    WHEN 'ironwood Animist Staff of Creeping Path' THEN '아이언우드 애니미스트 스태프: 크리핑 패스'
    WHEN 'ironwood Animist Staff of Mysticism' THEN '아이언우드 애니미스트 스태프: 미스티시즘'
    WHEN 'ironwood Animist Staff of Verdant Path' THEN '아이언우드 애니미스트 스태프: 버던트 패스'
    WHEN 'ironwood Eldritch Staff of Light' THEN '아이언우드 엘드리치 스태프: 라이트'
    WHEN 'ironwood Eldritch Staff of Magic' THEN '아이언우드 엘드리치 스태프: 매직'
    WHEN 'ironwood Eldritch Staff of Mana' THEN '아이언우드 엘드리치 스태프: 마나'
    WHEN 'ironwood Eldritch Staff of Void' THEN '아이언우드 엘드리치 스태프: 보이드'
  END,
  NULL,
  NULL,
  NULL,
  'korean-localization-low-level-equipment',
  NOW()
FROM itemtemplate it
WHERE it.Level BETWEEN 1 AND 20
  AND it.Item_Type BETWEEN 10 AND 28
  AND it.Name IN (
    'large round shield',
    'medium round shield',
    'large heater shield',
    'medium heater shield',
    'large block shield',
    'medium block shield',
    'elm large round shield',
    'elm medium round shield',
    'elm large heater shield',
    'elm medium heater shield',
    'elm large block shield',
    'elm medium block shield',
    'oaken large round shield',
    'oaken medium round shield',
    'oaken large heater shield',
    'oaken medium heater shield',
    'oaken large block shield',
    'oaken medium block shield',
    'hard large round shield',
    'hard medium round shield',
    'hard large heater shield',
    'hard medium heater shield',
    'hard large block shield',
    'hard medium block shield',
    'bronze short sword',
    'rowan short bow',
    'bronze two-handed sword',
    'dress robe',
    'fancy robe',
    'plain robe',
    'bronze great hammer',
    'bronze shod staff',
    'bronze war hammer',
    'bronze great sword',
    'Daring Leather Cap',
    'linen dress robe',
    'linen fancy robe',
    'linen plain robe',
    'rowan recurve bow',
    'elm short bow',
    'iron short sword',
    'iron two-handed sword',
    'iron great hammer',
    'iron shod staff',
    'iron war hammer',
    'iron great sword',
    'brocade dress robe',
    'brocade fancy robe',
    'brocade plain robe',
    'elm short recurve bow',
    'steel short sword',
    'steel two-handed sword',
    'steel great hammer',
    'steel shod staff',
    'steel war hammer',
    'steel great sword',
    'silk dress robe',
    'silk fancy robe',
    'silk plain robe',
    'alloy short sword',
    'ironwood short bow',
    'alloy two-handed sword',
    'alloy great hammer',
    'alloy shod staff',
    'alloy war hammer',
    'alloy great sword',
    'gossamer dress robe',
    'gossamer fancy robe',
    'gossamer plain robe',
    'Tattered Worn Robe',
    'two-handed sword',
    'Rawhide Torn Sleeves',
    'Torn Vest',
    'Trapper Cloak',
    'woolen dress robe',
    'Woolen Torn Pants',
    'Woolen Torn Sleeves',
    'rowan shod staff',
    'two-hand spiked mace',
    'great hammer',
    'Slightly Torn Vest',
    'Woolen Slightly Torn Sleeves',
    'Daring Leather Boots',
    'Daring Leather Gloves',
    'Daring Leather Jerkin',
    'Daring Leather Leggings',
    'Daring Leather Sleeves',
    'Daring Padded Boots',
    'Daring Padded Cap',
    'Daring Padded Gloves',
    'Daring Padded Pants',
    'Daring Padded Sleeves',
    'Daring Padded Vest',
    'Daring Studded Boots',
    'Daring Studded Cap',
    'Daring Studded Gloves',
    'Daring Studded Jerkin',
    'Daring Studded Leggings',
    'Daring Studded Sleeves',
    'great sword',
    'rowan great recurve bow',
    'rowan short recurve bow',
    'Tanned Barely Torn Cap',
    'elm Animist Staff of Arboreal Path',
    'elm Animist Staff of Creeping Path',
    'elm Animist Staff of Mysticism',
    'elm Animist Staff of Verdant Path',
    'elm Eldritch Staff of Light',
    'elm Eldritch Staff of Magic',
    'elm Eldritch Staff of Mana',
    'elm Eldritch Staff of Void',
    'ferrite two-handed sword',
    'ferrite big shillelagh',
    'elm shod staff',
    'ferrite two-hand spiked mace',
    'ferrite great hammer',
    'elm great recurve bow',
    'elm recurve bow',
    'ferrite great sword',
    'Midgard Spear',
    'Summoned Jewel',
    'oaken Animist Staff of Arboreal Path',
    'oaken Animist Staff of Creeping Path',
    'oaken Animist Staff of Mysticism',
    'oaken Animist Staff of Verdant Path',
    'oaken Eldritch Staff of Light',
    'oaken Eldritch Staff of Magic',
    'oaken Eldritch Staff of Mana',
    'oaken Eldritch Staff of Void',
    'quartz two-handed sword',
    'quartz big shillelagh',
    'oaken shod staff',
    'oaken short bow',
    'quartz two-hand spiked mace',
    'quartz great hammer',
    'Quartz Long Sword',
    'Fire Hardened Irewood Spear',
    'oaken great recurve bow',
    'oaken recurve bow',
    'oaken short recurve bow',
    'quartz great sword',
    'dolomite two-handed sword',
    'ironwood Animist Staff of Arboreal Path',
    'ironwood Animist Staff of Creeping Path',
    'ironwood Animist Staff of Mysticism',
    'ironwood Animist Staff of Verdant Path',
    'ironwood Eldritch Staff of Light',
    'ironwood Eldritch Staff of Magic',
    'ironwood Eldritch Staff of Mana',
    'ironwood Eldritch Staff of Void'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM languageitem li
    WHERE li.Language = 'KR'
      AND (
        li.TranslationId = it.Id_nb
        OR (it.TranslationId IS NOT NULL AND it.TranslationId <> '' AND li.TranslationId = it.TranslationId)
      )
  );
