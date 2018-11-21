var hijack = function(){
  console.log('Hooking to saveCSVtoFile...');
  GStool.saveCSVtoFile = function(){
    console.log('Converting:', arguments['1']);
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
      if (void 0 !== f.get(0).download) {
          var c = new Blob([json['kml']],{
              type: "application/vnd.google-earth.kml+xml;charset=utf-8;"
          })
            , g = URL.createObjectURL(c);
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
};

var script = document.createElement('script');
script.textContent = "(" + hijack.toString() + ")()";
document.head.appendChild(script);

