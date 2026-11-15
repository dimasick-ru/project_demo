document.querySelector('.mobile-menu')?.addEventListener('click', (event) => {
  const opened = document.body.classList.toggle('menu-open');
  event.currentTarget.setAttribute('aria-expanded', String(opened));
});
document.querySelectorAll('[data-json-example]').forEach((button) => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.jsonExample);
    if (input.value.trim() && input.value.trim() !== '[]') return;
    const item = button.dataset.kind === 'orders'
      ? {товар: '', количество: 1, закупочная_цена: 0, сумма: 0}
      : {номенклатура: '', количество: 1, цена: 0, сумма: 0};
    input.value = JSON.stringify([item], null, 2);
    input.focus();
  });
});

// Progressive enhancement: ordinary table inputs, with the original JSON kept available.
document.querySelectorAll('[data-json-example]').forEach((exampleButton) => {
  const input = document.getElementById(exampleButton.dataset.jsonExample);
  let positions;
  try {
    positions = JSON.parse(input.value || '[]');
    if (!Array.isArray(positions) || positions.some(p => !p || Array.isArray(p) || typeof p !== 'object')) return;
  } catch { return; }
  const order = exampleButton.dataset.kind === 'orders';
  const keys = order ? ['товар', 'количество', 'закупочная_цена', 'сумма'] : ['номенклатура', 'количество', 'цена', 'сумма'];
  // Unknown JSON layouts remain editable without silently replacing their fields.
  if (positions.some(p => Object.keys(p).some(key => !keys.includes(key)))) return;
  const names = JSON.parse(document.getElementById('nomenclature-options')?.textContent || '{}');
  const editor = document.createElement('div');
  editor.className = 'position-editor';
  const scroller = document.createElement('div');
  scroller.className = 'table-responsive';
  const table = document.createElement('table');
  table.className = 'table align-middle position-table';
  const header = table.createTHead().insertRow();
  ['Номенклатура', 'Количество', order ? 'Закупочная цена, ₽' : 'Цена, ₽', 'Сумма, ₽', ''].forEach(label => {
    const th = document.createElement('th'); th.textContent = label; th.scope = 'col'; header.append(th);
  });
  const body = table.createTBody();
  scroller.append(table); editor.append(scroller);
  const add = document.createElement('button');
  add.type = 'button'; add.className = 'btn btn-light btn-sm'; add.textContent = '＋ Добавить позицию';
  editor.append(add);
  const hint = document.createElement('p');
  hint.className = 'form-text mt-2'; hint.textContent = 'Укажите сумму каждой позиции и общую сумму документа. В прототипе они вводятся вручную.';
  editor.append(hint);
  const sync = () => { input.value = JSON.stringify(positions, null, 2); };
  const render = () => {
    body.replaceChildren();
    positions.forEach((position, index) => {
      const row = body.insertRow();
      keys.forEach((key, keyIndex) => {
        const control = document.createElement(keyIndex === 0 ? 'select' : 'input');
        control.className = keyIndex === 0 ? 'form-select' : 'form-control';
        control.setAttribute('aria-label', `${header.cells[keyIndex].textContent}, строка ${index + 1}`);
        if (keyIndex === 0) {
          const labels = ['', ...new Set([...Object.values(names), String(position[key] || '')])];
          labels.forEach(name => { const option = document.createElement('option'); option.value = name; option.textContent = name || 'Выберите товар / услугу'; control.append(option); });
        } else {
          control.type = 'number'; control.min = '0'; control.step = keyIndex === 1 ? '0.0001' : '0.01';
          control.max = '9999999999.99'; control.required = true;
        }
        control.value = position[key] ?? (keyIndex === 0 ? '' : 0);
        control.addEventListener('change', () => {
          position[key] = keyIndex === 0 ? control.value : Number(control.value);
          sync();
        });
        row.insertCell().append(control);
      });
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'btn btn-light btn-sm'; remove.textContent = '×';
      remove.setAttribute('aria-label', `Удалить позицию ${index + 1}`);
      remove.addEventListener('click', () => { positions.splice(index, 1); sync(); render(); });
      row.insertCell().append(remove);
    });
  };
  add.addEventListener('click', () => {
    positions.push(Object.fromEntries(keys.map((key, index) => [key, index === 0 ? '' : index === 1 ? 1 : 0])));
    sync(); render();
  });
  input.before(editor);
  input.hidden = true;
  input.nextElementSibling.hidden = true;
  exampleButton.hidden = true;
  render();
});
