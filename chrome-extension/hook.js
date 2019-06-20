var hijack = function(){
  console.log('Adding js to document');

  GStool.exportVLMtoFile = function(){
    console.log('Converting:', arguments['1']);
    arguments['unit'] = GStool.unit;
    arguments['headingMode'] = GStool.currMission.headingMode;
    arguments['finishAction'] = GStool.currMission.finishAction;
    arguments['pathMode'] = GStool.currMission.pathMode;
    arguments['horizontalSpeed'] = GStool.currMission.horizontalSpeed;
    arguments['rcSpeed'] = GStool.currMission.rcSpeed;
    arguments['defaultCurveSize'] = GStool.curves.defaultCurveSize;
    arguments['defaultGimbalPitchMode'] = GStool.curves.defaultGimbalPitchMode;
    arguments['defspeed'] = GStool.currMission.horizontalSpeed;
    arguments['droneModel'] = GStool.extension.droneModel;
    arguments['customFOV'] = GStool.extension.customFOV;
    arguments['maxWPDist'] = GStool.extension.maxWPDist;
    h = new Headers();
    h.append("Content-Type", "application/json");
    fetch('https://vlm.baz.pw/convert', {
      method : "POST",
      headers: h,
      body: JSON.stringify(arguments)
    }).then(function(response){
      var contentType = response.headers.get("content-type");
      if(contentType && contentType.includes("application/json")){
        return response.json();
      }throw new TypeError("Invalid server response");
    }).then(function(json){
      console.log('Converted:', json['mission'])
      var f = $("<a>");
      if (void 0 !== f.get(0).download){
        var c = new Blob([json['kml']],{ type: "application/vnd.google-earth.kml+xml;charset=utf-8;" }),
        g = URL.createObjectURL(c);
        f.get(0).setAttribute("href", g),
        f.get(0).setAttribute("download", json['mission']+'.kml'),
        f.get(0).style.opacity = 0,
        $("body").append(f),
        f.show().focus();
        var h = document.createEvent("MouseEvents");
        h.initEvent("click", !1, !1),
        f.get(0).dispatchEvent(h),
        f.hide(),
        f.remove();
      };
    }).catch(function(error){
      console.log(error);
      alert("Can't convert to kml:", error);
    });
  };

  GStool.saveCSVtoFile = (function(_super){
    return function(){
      return GStool.overriden ? GStool.exportVLMtoFile.apply(this, arguments) :  _super.apply(this, arguments);
    };
  })(GStool.saveCSVtoFile);

  GStool.exportVLM = function(){
    GStool.overriden = 1;
    GStool.exportCSV.apply(this, arguments);
    GStool.overriden = 0;
  };

  $(document).on("mouseover", ".mission-dropdown-toggle", function(){
    if (GStool.hookmenu) return;
    console.log('Adding menu item');
    $('#dd-miss-ul').append('<li><a id="mn-exportvlm" href="javascript:;"><font color="red">Export as VLM</font></a></li>');
    $(document).on("click", "#mn-exportvlm", function(){ $(".mission-dropdown-toggle").next().css("display", "none"), GStool.exportVLM.call(GStool) });
    GStool.hookmenu = 1;
  });
};

var script = document.createElement('script');
script.textContent = "(" + hijack.toString() + ")()";
document.head.appendChild(script);

function setting(v, x){
  var settings = document.createElement('script');
  settings.textContent = "(function(x){ if (!GStool.extension) GStool.extension = {}; GStool.extension." + v + " = x; })(\"" + x + "\")";
  document.head.appendChild(settings);
  document.head.removeChild(settings);
  console.log("Updated " + v + " to: " + x);
}

chrome.storage.local.get({
  droneModel: 'm2phq',
  customFOV: 90.0,
  maxWPDist: 1000
}, function(items){
  setting("droneModel", items.droneModel);
  setting("customFOV", items.customFOV);
  setting("maxWPDist", items.maxWPDist);
});

chrome.storage.local.onChanged.addListener(function (items){
  if (items.droneModel)
    setting("droneModel", items.droneModel.newValue);
  if (items.customFOV)
    setting("customFOV", items.customFOV.newValue);
  if (items.maxWPDist)
    setting("maxWPDist", items.maxWPDist.newValue);
});

