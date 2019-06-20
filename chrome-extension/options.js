function save_maxwpdist() {
  var fill = document.getElementById('maxwpdist').value;
  chrome.storage.local.set({ maxWPDist: fill });
}

function save_drone() {
  var drone = document.getElementById('drone');
  var model = drone.options[drone.selectedIndex].value
  if (model == "custom")
    document.getElementById('customfov').hidden = false;
  else
    document.getElementById('customfov').hidden = true;
  chrome.storage.local.set({ droneModel: model });
}

function save_customfov() {
  var fov = document.getElementById('customfov').value;
  chrome.storage.local.set({ customFOV: fov });
}

function restore_options() {
  chrome.storage.local.get({
    droneModel: 'm2phq',
    customFOV: 90.0,
    maxWPDist: 1000
  }, function(items) {
    drone = document.getElementById('drone');
    for (var i = 0; i < drone.options.length; i++) {
      var option = drone.options[i];
      if (option.value == items.droneModel)
        option.selected = true;
      else
        option.selected = false;
    };
    document.getElementById('maxwpdist').value = items.maxWPDist;
    document.getElementById('customfov').value = items.customFOV;
  });
}

document.addEventListener('DOMContentLoaded', restore_options);
document.getElementById('drone').addEventListener("change", save_drone);
document.getElementById('customfov').addEventListener("change", save_customfov);
document.getElementById('maxwpdist').addEventListener("change", save_maxwpdist);

