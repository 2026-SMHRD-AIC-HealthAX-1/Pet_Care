package com.smhrd.myapp.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.service.PetService;

import java.util.List;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/pets")
public class PetController {
    private final PetService petService;

    @PostMapping
    public PetEntity createPet(@RequestParam String pName,
                               @RequestParam char pGender,
                               @RequestParam String pSpecies,
                               @RequestParam Integer pAge,
                               @RequestParam Integer pWeight,
                               @RequestParam String pSpec,
                               @RequestParam char isMule,
                               @RequestParam char isVaccin_1,
                               @RequestParam char isVaccin_2,
                               @RequestParam char isVaccin_3) {
        return petService.savePet(pName, pGender, pSpecies, pAge, pWeight, pSpec, isMule, isVaccin_1, isVaccin_2, isVaccin_3);
    }

    @GetMapping
    public List listPets() {
        return petService.getAllPets();
    }
}