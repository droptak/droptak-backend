function removeTak(id){
	//send delete to server
        if (!confirm("Are you sure you want to permanently delete this tak?")) return;
        $.ajax({
            url: '/api/v1/tak/' + id,
            type: 'DELETE',
            success: function (result) {
                self.taks.remove(tak);
                self.selected(null);
                console.log(result);
		window.location.reload(true);
            }
        });
}
