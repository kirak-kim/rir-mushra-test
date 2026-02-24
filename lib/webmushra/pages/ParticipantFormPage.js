/*************************************************************************
         (C) Copyright AudioLabs 2017 

This source code is protected by copyright law and international treaties. This source code is made available to You subject to the terms and conditions of the Software License for the webMUSHRA.js Software. Said terms and conditions have been made available to You prior to Your download of this source code. By downloading this source code You agree to be bound by the above mentionend terms and conditions, which can also be found here: https://www.audiolabs-erlangen.de/resources/webMUSHRA. Any unauthorised use of this source code may result in severe civil and criminal penalties, and will be prosecuted to the maximum extent possible under law. 

**************************************************************************/

function ParticipantFormPage(_pageManager, _pageTemplateRenderer, _session, _pageConfig) {
  this.pageManager = _pageManager;
  this.pageTemplateRenderer = _pageTemplateRenderer;
  this.session = _session;
  this.pageConfig = _pageConfig;

  if (this.pageConfig.questionnaire === undefined) {
    this.pageConfig.questionnaire = [];
  }
  this.errorDiv = $("<div style='color:red; font-weight:bold;'></div>");
}

ParticipantFormPage.prototype.getName = function () {
  return this.pageConfig.name;
};

ParticipantFormPage.prototype._getParticipantValue = function(name) {
  var idx = this.session.participant.name.indexOf(name);
  if (idx >= 0) {
    return this.session.participant.response[idx];
  }
  return null;
};

ParticipantFormPage.prototype._setParticipantValue = function(name, value) {
  var idx = this.session.participant.name.indexOf(name);
  if (idx >= 0) {
    this.session.participant.response[idx] = value;
  } else {
    this.session.participant.name.push(name);
    this.session.participant.response.push(value);
  }
};

ParticipantFormPage.prototype._validate = function() {
  var i;
  var validCount = 0;
  for (i = 0; i < this.pageConfig.questionnaire.length; ++i) {
    var element = this.pageConfig.questionnaire[i];
    var value = null;
    if (element.type === "text" || element.type === "number" || element.type === "long_text") {
      value = $("#" + element.name).val();
    } else if (element.type === "likert") {
      value = $("input[name='" + element.name + "__response']:checked").val();
    }

    if ((value !== undefined && value !== null && value !== "") || element.optional === true) {
      validCount++;
    }
  }

  if (validCount === this.pageConfig.questionnaire.length) {
    this.pageTemplateRenderer.unlockNextButton();
    this.errorDiv.text("");
  } else {
    this.pageTemplateRenderer.lockNextButton();
    if (this.pageConfig.questionnaire.length > 0) {
      this.errorDiv.text(this.pageConfig.validationMessage || "Please complete all required fields.");
    }
  }
};

ParticipantFormPage.prototype.render = function (_parent) {
  if (this.pageConfig.content) {
    _parent.append(this.pageConfig.content);
  }

  var table = $("<table align='center'></table>");
  _parent.append(table);

  var i;
  for (i = 0; i < this.pageConfig.questionnaire.length; ++i) {
    var element = this.pageConfig.questionnaire[i];
    var existingValue = this._getParticipantValue(element.name);

    if (element.type === "text") {
      var input = $("<input id='" + element.name + "' />");
      if (existingValue !== null) {
        input.val(existingValue);
      }
      table.append($("<tr></tr>").append(
        $("<td><strong>" + element.label + "</strong></td>"),
        $("<td></td>").append(input)
      ));
    } else if (element.type === "number") {
      var numberInput = $("<input id='" + element.name + "' type='number' data-inline='true'/>");
      if (element.min !== undefined) {
        numberInput.attr("min", element.min);
      }
      if (element.max !== undefined) {
        numberInput.attr("max", element.max);
      }
      if (existingValue !== null) {
        numberInput.val(existingValue);
      } else if (element.default !== undefined) {
        numberInput.val(element.default);
      }
      table.append($("<tr></tr>").append(
        $("<td><strong>" + element.label + "</strong></td>"),
        $("<td></td>").append(numberInput)
      ));
    } else if (element.type === "likert") {
      var likert = new LikertScale(element.response, element.name + "_");
      var td = $("<td></td>");
      table.append($("<tr></tr>").append(
        $("<td><strong>" + element.label + "</strong></td>"),
        td
      ));
      likert.render(td);
    } else if (element.type === "long_text") {
      var ta = $("<textarea id='" + element.name + "' name='" + element.name + "'></textarea>");
      if (existingValue !== null) {
        ta.val(existingValue);
      }
      table.append($("<tr></tr>").append(
        $("<td style='vertical-align:top'><strong>" + element.label + "</strong></td>"),
        $("<td></td>").append(ta)
      ));
    }
  }

  _parent.append(this.errorDiv);

  var self = this;
  _parent.find("input, textarea").bind("change input", function() {
    self._validate();
  });
  _parent.find("input[type='radio']").bind("change", function() {
    self._validate();
  });

  // Restore pre-selected likert values after rendering.
  for (i = 0; i < this.pageConfig.questionnaire.length; ++i) {
    var element2 = this.pageConfig.questionnaire[i];
    if (element2.type === "likert") {
      var existing = this._getParticipantValue(element2.name);
      if (existing !== null) {
        $("input[name='" + element2.name + "__response'][value='" + existing + "']").prop("checked", true);
      }
    }
  }
};

ParticipantFormPage.prototype.load = function () {
  this.pageTemplateRenderer.lockNextButton();
  this._validate();
};

ParticipantFormPage.prototype.save = function () {
  var i;
  for (i = 0; i < this.pageConfig.questionnaire.length; ++i) {
    var element = this.pageConfig.questionnaire[i];
    var value = null;
    if (element.type === "text" || element.type === "number" || element.type === "long_text") {
      value = $("#" + element.name).val();
    } else if (element.type === "likert") {
      value = $("input[name='" + element.name + "__response']:checked").val();
    }
    if (value !== undefined && value !== null && value !== "") {
      this._setParticipantValue(element.name, value);
    }
  }
};
