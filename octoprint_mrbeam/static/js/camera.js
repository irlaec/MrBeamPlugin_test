$(function(){

	function CameraViewModel(params) {
		var self = this;

		self.settings = params[0];
		self.workingArea = params[1];
        self.profile = params[2];

        self.camera_offset_x = ko.observable(0);
		self.camera_offset_y = ko.observable(0);
		self.camera_scale = ko.observable(1.0);
		self.camera_rotation = ko.observable(0.0);

        self.webCamImageElem = undefined;
        self.lastImageLoaded = '/plugin/mrbeam/static/img/beam-cam-static.jpg';

		self.camTransform = ko.computed(function(){
			return "scale("+self.camera_scale()+") rotate("+self.camera_rotation()+"deg) translate("+self.camera_offset_x()+"px, "+self.camera_offset_y()+"px)"
		});

		self.onStartup = function(){
            self.webCamImageElem = $("#webcam_image");

            self.webCamImageElem.error(function() {
                if (self.lastImageLoaded) {
                    // this will trigger onLoad event
                    self.webCamImageElem.attr('src', self.lastImageLoaded);
                }
            });

            self.webCamImageElem.load(function() {
                self.lastImageLoaded = self.webCamImageElem.attr('src');
            });

            self.onTabChange('#workingarea', '#notab');
		};

		self.onAfterBinding = function(){
			self.initCameraCalibration();
		};

		self.onBrowserTabVisibilityChange = function(state){
			var currentTab = $('#mrbeam-main-tabs li.active a').attr('href');
			if(typeof currentTab !== undefined && currentTab === "#workingarea"){
				if(state === true){
					self.onTabChange('#workingarea', '#notab');
				}
				if(state === false){
					self.onTabChange('#notab', '#workingarea');
				}
			}
		};

		self.onTabChange = function (current, previous) {
            if (current === "#workingarea") {
                if (self.webcamDisableTimeout != undefined) {
                    clearTimeout(self.webcamDisableTimeout);
                }
                var webcamImage = self.webCamImageElem;
                var currentSrc = webcamImage.attr("src");

                if (currentSrc === undefined || currentSrc === "none" || currentSrc.trim() === "") {
                    var newSrc = CONFIG_WEBCAM_STREAM;
                    if (CONFIG_WEBCAM_STREAM.lastIndexOf("?") > -1) {
                        newSrc += "&";
                    } else {
                        newSrc += "?";
                    }
                    newSrc += new Date().getTime();
//                    console.log("webcam src set", newSrc);
                    webcamImage.attr("src", newSrc);
                }
                photoupdate = setInterval(myTimer, 5000);
                function myTimer() {
                    var newSrc = CONFIG_WEBCAM_STREAM;
                    if (CONFIG_WEBCAM_STREAM.lastIndexOf("?") > -1) {
                        newSrc += "&";
                    } else {
                        newSrc += "?";
                    }
                    newSrc += new Date().getTime();
                   // console.log("webcam src set", newSrc);
                    webcamImage.attr("src", newSrc);
                }
                console.log("webcam enabled");
            } else if (previous === "#workingarea") {
                // only disable webcam stream if tab is out of focus for more than 5s, otherwise we might cause
                // more load by the constant connection creation than by the actual webcam stream
                self.webcamDisableTimeout = setTimeout(function () {
                    self.webCamImageElem.css("background-image", "none");
                }, 5000);
                window.clearInterval(photoupdate)
            }
        };


		self.initCameraCalibration = function(){
			var s = self.settings.settings.plugins.mrbeam;
			s.camera_offset_x.subscribe(function(newValue) {
				self.camera_offset_x(newValue);
			});
			s.camera_offset_y.subscribe(function(newValue) {
				self.camera_offset_y(newValue);
			});
			s.camera_scale.subscribe(function(newValue) {
				self.camera_scale(newValue);
			});
			s.camera_rotation.subscribe(function(newValue) {
				self.camera_rotation(newValue);
			});

			s.camera_offset_x.notifySubscribers(s.camera_offset_x());
			s.camera_offset_y.notifySubscribers(s.camera_offset_y());
			s.camera_scale.notifySubscribers(s.camera_scale());
			s.camera_rotation.notifySubscribers(s.camera_rotation());

		};
	}


    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([CameraViewModel,
		["settingsViewModel", "workingAreaViewModel", "laserCutterProfilesViewModel"],
		[
			document.getElementById("webcam_wrapper"),
			document.getElementById("settings_camera_calibration")
		]
	]);

});
