package com.smhrd.myapp.controller;

import lombok.RequiredArgsConstructor;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.repository.PetRepository;

@Controller
public class PetController {

    private final PetRepository repo;

	PetController(PetRepository repo) {
		this.repo = repo;
	}
	
	@PostMapping("/petinsert") 
	public String petinsert(PetEntity pet, Model model) 
	{ 
		repo.save(pet);
	  
		model.addAttribute("model", model);
	  
		return "redirect:/petmanagement"; 
	}
	  
	  
//	@GetMapping
//	public List listPets() { return petService.getAllPets(); }
}