/*************************************************************************
         (C) Copyright AudioLabs 2017

This source code is protected by copyright law and international treaties. This source code is made available to You subject to the terms and conditions of the Software License for the webMUSHRA.js Software. Said terms and conditions have been made available to You prior to Your download of this source code. By downloading this source code You agree to be bound by the above mentionend terms and conditions, which can also be found here: https://www.audiolabs-erlangen.de/resources/webMUSHRA. Any unauthorised use of this source code may result in severe civil and criminal penalties, and will be prosecuted to the maximum extent possible under law.

**************************************************************************/

function DataSender(config) {
  this.target = config.remoteService;
  this.googleFormUrl = config.googleFormUrl;
  this.googleFormEntryId = config.googleFormEntryId;
}

DataSender.prototype._sendGoogleForm = function(_session, _sessionJSON) {
  if (!this.googleFormUrl || !this.googleFormEntryId) {
    return;
  }

  try {
    if (window.fetch && window.FormData) {
      var formData = new FormData();
      formData.append(this.googleFormEntryId, _sessionJSON);
      fetch(this.googleFormUrl, {
        method: "POST",
        mode: "no-cors",
        body: formData
      }).catch(function(e) {
        console.log("Google Form send failed:", e);
      });
      return;
    }

    // Fallback: hidden form submit (fire-and-forget).
    var iframe = document.createElement("iframe");
    iframe.name = "google_form_sink_" + Date.now();
    iframe.style.display = "none";
    document.body.appendChild(iframe);

    var form = document.createElement("form");
    form.method = "POST";
    form.action = this.googleFormUrl;
    form.target = iframe.name;
    form.style.display = "none";

    var input = document.createElement("textarea");
    input.name = this.googleFormEntryId;
    input.value = _sessionJSON;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();

    setTimeout(function() {
      try {
        document.body.removeChild(form);
        document.body.removeChild(iframe);
      } catch (e) {}
    }, 1000);
  } catch (e) {
    console.log("Google Form send setup failed:", e);
  }
};

DataSender.prototype.send = function(_session) {
  var sessionJSON = JSON.stringify(_session);
  var localSendError = false;

  this._sendGoogleForm(_session, sessionJSON);

  if (!this.target) {
    return false;
  }

  var httpReq = new XMLHttpRequest();
  var params = "sessionJSON=" + encodeURIComponent(sessionJSON);
  try {
    httpReq.open("POST", this.target, false);  // synchron
    httpReq.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    httpReq.send(params);
  }
  catch (e) {
    console.log(httpReq.responseText);
    return true;
  }
  if(httpReq.responseText != "" || httpReq.status != 200){
    console.log(httpReq.responseText);
    localSendError = true;
  }else{
    localSendError = false;
  }
  return localSendError;
};
