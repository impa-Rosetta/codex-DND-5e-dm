const $ = id => document.getElementById(id);
const abilities = {str: '力量', dex: '敏捷', con: '体质', int: '智力', wis: '感知', cha: '魅力'};
const labels = {human: '人类', fighter: '战士', barbarian: '野蛮人', rogue: '游荡者', monk: '武僧', acolyte: '侍僧',
  old_mill: '旧磨坊路口', forest_path: '林中岔路',
  second_wind: '第二春', rage: '狂暴次数', hit_dice_d10: '生命骰 d10',
  hit_dice_d12: '生命骰 d12', hit_dice_d8: '生命骰 d8',
  ammunition_arrow: '箭矢', recoverable_arrow: '可找回箭矢'};
let lastRevision = -1;

function node(tag, className, content) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = content;
  return element;
}

function render(data) {
  $('campaign-name').textContent = data.name;
  $('scene-name').textContent = data.scene?.name || '—';
  $('connection').textContent = '已同步 · #' + data.revision;

  const character = data.character;
  $('character-empty').hidden = !!character;
  $('character-body').hidden = !character;
  if (character) {
    const derived = character.derived || {};
    $('character-name').textContent = character.name || '无名冒险者';
    $('character-level').textContent = '1 级';
    $('character-meta').textContent = [
      character.source_choices?.race,
      character.source_choices?.class,
      character.source_choices?.background,
    ].filter(Boolean).map(id => labels[id] || id).join(' · ');
    $('hp').textContent = (character.resources?.hp?.current ?? '—') + ' / ' +
                          (character.resources?.hp?.max ?? '—');
    $('ac').textContent = derived.ac ?? '—';
    $('speed').textContent = (derived.speed ?? '—') + ' ft';
    $('ability-grid').replaceChildren(...Object.entries(abilities).map(([id, label]) => {
      const box = node('div', '', '');
      box.append(node('span', '', label), node('strong', '', String(derived.abilities?.[id] ?? '—')));
      return box;
    }));
    $('resources').replaceChildren(...Object.entries(character.resources || {})
      .filter(([id]) => !['hp', 'temp_hp'].includes(id))
      .map(([id, value]) => node('p', '', `${labels[id] || id}: ${value.current} / ${value.max}`)));
  }

  $('map').replaceChildren(...(data.scene?.discovered_locations || [])
    .map(id => node('span', 'node' + (id === data.scene.location_id ? ' current' : ''),
      labels[id] || id)));

  const fight = data.combat;
  $('round').textContent = fight ? '第 ' + fight.round + ' 轮' : '未进入战斗';
  const combatants = $('combatants');
  if (fight) {
    combatants.className = '';
    combatants.replaceChildren(...fight.combatants.map((unit, index) => {
      const position = Array.isArray(unit.position) ? `格 (${unit.position.join(', ')})` : '位置未知';
      const reaction = unit.reaction_used ? ' · 反应已用' : '';
      const dodge = unit.dodging ? ' · 闪避中' : '';
      const rage = fight.rage_active && unit.combatant_id === character?.id ? ' · 狂暴中' : '';
      return node('div', 'combatant' + (index === fight.turn_index ? ' active' : ''),
        `${unit.name} · HP ${unit.hp} · AC ${unit.ac} · ${position}${reaction}${dodge}${rage}`);
    }));
  } else {
    combatants.className = 'empty';
    combatants.textContent = '平静时刻';
  }

  $('event-list').replaceChildren(...(data.events || []).slice().reverse().map(event => {
    const item = node('li', '', event.view?.summary || event.type);
    item.append(node('small', '', `#${event.seq} · ${event.event_id.slice(0, 8)}`));
    return item;
  }));
}

async function refresh() {
  try {
    const response = await fetch('/api/snapshot', {cache: 'no-store'});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    if (data.revision !== lastRevision) {
      render(data);
      lastRevision = data.revision;
    }
  } catch (_error) {
    $('connection').textContent = '连接中断 · 重试中';
  }
}

refresh();
setInterval(refresh, 5000);
if ('EventSource' in window) {
  const stream = new EventSource('/api/events');
  stream.addEventListener('revision', () => refresh());
  stream.onerror = () => { $('connection').textContent = '重连中'; };
}
